"""Cohere LLM orchestrator for the clinical insight pipeline.

Responsibilities:
- Call Cohere once per patient (avoids token-limit truncation)
- Parse and normalize the per-patient response
- Aggregate insights into a deterministic DashboardSummary
- Fall back to the deterministic engine on any per-patient failure

See also:
- prompt.py          — SYSTEM_PROMPT constant
- patient_transformer.py — data simplification + response normalization
- fallback_engine.py — deterministic fallback analysis
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List

import cohere

from app.config import settings
from app.models.schemas import (
    ConversionFunnelSummary,
    DashboardResponse,
    DashboardSummary,
    PatientInsight,
    ProgressionStatus,
    RiskLevel,
)
from app.services.fallback_engine import generate_fallback_response
from app.services.patient_transformer import (
    extract_patient_data,
    normalize_patient_data,
    simplify_patients,
)
from app.services.prompt import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Initialize Cohere async client — None if key is not configured
cohere_client = None
if settings.cohere_api_key:
    cohere_client = cohere.AsyncClientV2(api_key=settings.cohere_api_key)

# Appended to SYSTEM_PROMPT for single-patient mode
_SINGLE_PATIENT_SUFFIX = (
    "\n\nIMPORTANT: You will receive ONE patient at a time. "
    "Return a JSON object with a single 'patient' key containing one PatientInsight. "
    "Do NOT include 'summary', 'patients' array, or 'generated_at'. Example structure:\n"
    "{\"patient\": { ...all PatientInsight fields... }}\n\n"
    "CRITICAL RULES:\n"
    "1. patient_name: copy EXACTLY from the input 'name' field -- NEVER null.\n"
    "2. age: copy EXACTLY from the input 'age' field as an integer -- NEVER null.\n"
    "3. gender: copy EXACTLY from the input 'gender' field -- NEVER null.\n"
    "4. patient_id: copy EXACTLY from the input 'id' field.\n"
    "5. For source in next_actions, risk_flags, and progression_metrics: use a SINGLE "
    "object {\"type\": \"...\", \"description\": \"...\", \"visit_number\": N} -- NOT a list."
)

# Max retries for transient Cohere errors
_MAX_RETRIES = 2
_RETRY_DELAYS = [1.0, 3.0]  # seconds


def _sanitize_response_text(text: str) -> str:
    """Clean up LLM response text before JSON parsing.
    
    Handles:
    - Markdown code fences (```json ... ```)
    - BOM characters
    - Trailing commas before } or ]
    - Leading/trailing whitespace
    """
    text = text.strip()
    
    # Remove BOM
    text = text.lstrip('\ufeff')
    
    # Remove markdown code fences
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    
    text = text.strip()
    
    # Remove trailing commas before } or ]
    text = re.sub(r',\s*([}\]])', r'\1', text)
    
    return text


async def _call_cohere_with_retry(messages: list) -> str:
    """Call Cohere API with retry logic for transient errors."""
    last_error = None
    
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = await cohere_client.chat(
                model="command-r-plus-08-2024",
                messages=messages,
                response_format={"type": "json_object"},
            )
            return response.message.content[0].text.strip()
        
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            
            # Only retry on transient errors (5xx, rate limit, timeout)
            is_retryable = any(kw in error_str for kw in [
                "500", "502", "503", "rate limit", "timeout", "overloaded",
                "internal server error", "service unavailable"
            ])
            
            if is_retryable and attempt < _MAX_RETRIES:
                delay = _RETRY_DELAYS[attempt]
                logger.warning(
                    f"Cohere API error (attempt {attempt + 1}/{_MAX_RETRIES + 1}): {e}. "
                    f"Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
            else:
                raise
    
    raise last_error  # Should never reach here, but safety net


async def analyze_all_patients(patients: List[Dict[str, Any]]) -> DashboardResponse:
    """Analyze each patient individually with Cohere, then aggregate the summary.

    - Processes one patient at a time to avoid JSON truncation from token limits.
    - Falls back to the deterministic engine for any patient that fails.
    - Summary metrics are always computed deterministically from insight objects.
    """
    if not cohere_client:
        logger.warning("Cohere API key not configured. Returning deterministic response.")
        return generate_fallback_response(patients)

    today = datetime.utcnow().strftime("%Y-%m-%d")
    simplified_patients = simplify_patients(patients)
    per_patient_prompt = SYSTEM_PROMPT + _SINGLE_PATIENT_SUFFIX

    semaphore = asyncio.Semaphore(5)

    async def _process_patient(i: int, simplified: Dict[str, Any], raw_patient: Dict[str, Any]) -> PatientInsight:
        patient_id = simplified.get("id", f"P-{i+1:04d}")
        
        async with semaphore:
            try:
                messages = [
                    {"role": "system", "content": per_patient_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Today's date is {today}. "
                            f"Analyze this ONE patient and return their clinical insight.\n\n"
                            f"{json.dumps(simplified, indent=2)}"
                        ),
                    },
                ]
                
                response_text = await _call_cohere_with_retry(messages)
                response_text = _sanitize_response_text(response_text)
                
                parsed = json.loads(response_text)
                patient_data = extract_patient_data(parsed)
                patient_data = normalize_patient_data(patient_data, simplified)
                
                # Validate against Pydantic schema
                insight = PatientInsight(**patient_data)
                
                logger.info(
                    f"{patient_id} — risk={insight.risk_level}, "
                    f"variance={insight.care_path_variance.detected}, "
                    f"conversion={insight.conversion_status.admission_status}"
                )
                return insight
                
            except json.JSONDecodeError as e:
                logger.warning(f"Cohere returned invalid JSON for {patient_id}: {e}. Using deterministic fallback.")
            except Exception as e:
                logger.warning(f"Cohere failed/invalid for {patient_id}: {e}. Using deterministic fallback.")
                
            # Fallback on any error
            fallback = generate_fallback_response([raw_patient])
            return fallback.patients[0] if fallback.patients else None

    # Run all tasks concurrently
    tasks = [
        _process_patient(i, simplified_patients[i], patients[i])
        for i in range(len(simplified_patients))
    ]
    results = await asyncio.gather(*tasks)

    all_insights = []
    fallback_count = 0
    for r in results:
        if r is None:
            fallback_count += 1
        else:
            all_insights.append(r)
            # We can't strictly distinguish fallback from cohere success here without altering the object,
            # but since we log the errors in _process_patient, it's fine.

    if not all_insights:
        logger.error("No insights generated. Returning full deterministic response.")
        return generate_fallback_response(patients)

    summary = _aggregate_summary(all_insights)
    logger.info(
        f"Analysis complete — {len(all_insights)} patients, "
        f"variance={summary.care_path_variance_count}, "
        f"high_risk={summary.high_risk_count}"
    )

    risk_order = {RiskLevel.HIGH: 0, RiskLevel.MEDIUM: 1, RiskLevel.LOW: 2}
    all_insights.sort(key=lambda x: risk_order.get(x.risk_level, 1))
    for rank, ins in enumerate(all_insights):
        ins.suggested_priority_rank = rank + 1

    return DashboardResponse(
        summary=summary,
        patients=all_insights,
        generated_at=datetime.utcnow(),
        from_cache=False,
    )


def _aggregate_summary(insights: List[PatientInsight]) -> DashboardSummary:
    """Deterministically compute DashboardSummary from a list of PatientInsight objects."""
    high = sum(1 for i in insights if i.risk_level == RiskLevel.HIGH)
    worsening = sum(1 for i in insights if i.progression_status == ProgressionStatus.WORSENING)
    variance_count = sum(1 for i in insights if i.care_path_variance.detected)
    pending_inv = sum(
        i.pending_actions_summary.pending_procedures + i.pending_actions_summary.pending_labs
        for i in insights
    )

    # Conversion barrier count
    barrier_count = sum(
        1 for i in insights
        if i.conversion_status.barrier is not None
    )

    cohort_counts: Dict[str, int] = {}
    for i in insights:
        bucket = i.cohort_bucket.value if hasattr(i.cohort_bucket, "value") else str(i.cohort_bucket)
        cohort_counts[bucket] = cohort_counts.get(bucket, 0) + 1

    funnel_total = sum(1 for i in insights if i.conversion_status.procedure_advised)
    funnel_contacted = sum(
        1 for i in insights
        if i.conversion_status.admission_status in ("Converted", "In Progress", "Declined")
    )
    funnel_interested = sum(1 for i in insights if i.conversion_status.admission_status == "In Progress")
    funnel_converted = sum(1 for i in insights if i.conversion_status.admission_status == "Converted")
    funnel_declined = sum(1 for i in insights if i.conversion_status.admission_status == "Declined")
    funnel_pending = max(0, funnel_total - funnel_contacted)

    return DashboardSummary(
        total_patients=len(insights),
        high_risk_count=high,
        worsening_count=worsening,
        care_path_variance_count=variance_count,
        pending_investigations=pending_inv,
        cohort_distribution=cohort_counts,
        conversion_barrier_count=barrier_count,
        pending_procedures_count=sum(i.pending_actions_summary.pending_procedures for i in insights),
        conversion_funnel=ConversionFunnelSummary(
            total_advised=funnel_total,
            contacted=funnel_contacted,
            interested=funnel_interested,
            converted=funnel_converted,
            declined=funnel_declined,
            pending=funnel_pending,
        ),
    )
