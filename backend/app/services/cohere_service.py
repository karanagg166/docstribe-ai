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

import json
import logging
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

# Initialize Cohere client — None if key is not configured
cohere_client = None
if settings.cohere_api_key:
    cohere_client = cohere.ClientV2(api_key=settings.cohere_api_key)

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

    all_insights: List[PatientInsight] = []
    fallback_count = 0

    for i, simplified in enumerate(simplified_patients):
        raw_patient = patients[i]
        patient_id = simplified.get("id", f"P-{i+1:04d}")

        try:
            response = cohere_client.chat(
                model="command-r-plus-08-2024",
                messages=[
                    {"role": "system", "content": per_patient_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Today's date is {today}. "
                            f"Analyze this ONE patient and return their clinical insight.\n\n"
                            f"{json.dumps(simplified, indent=2)}"
                        ),
                    },
                ],
                response_format={"type": "json_object"},
            )

            response_text = response.message.content[0].text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:-3]
            elif response_text.startswith("```"):
                response_text = response_text[3:-3]

            parsed = json.loads(response_text)
            patient_data = extract_patient_data(parsed)
            patient_data = normalize_patient_data(patient_data, simplified)
            insight = PatientInsight(**patient_data)

            all_insights.append(insight)
            logger.info(
                f"{patient_id} — risk={insight.risk_level}, "
                f"variance={insight.care_path_variance.detected}, "
                f"conversion={insight.conversion_status.admission_status}"
            )

        except Exception as e:
            logger.warning(f"Cohere failed for {patient_id}: {e}. Using deterministic fallback.")
            fallback_count += 1
            fallback = generate_fallback_response([raw_patient])
            if fallback.patients:
                all_insights.append(fallback.patients[0])

    if not all_insights:
        logger.error("No insights generated. Returning full deterministic response.")
        return generate_fallback_response(patients)

    summary = _aggregate_summary(all_insights)
    logger.info(
        f"Analysis complete — {len(all_insights)} patients, "
        f"variance={summary.care_path_variance_count}, "
        f"high_risk={summary.high_risk_count}, "
        f"fallbacks={fallback_count}"
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
    funnel_pending = max(0, funnel_contacted - funnel_interested - funnel_converted - funnel_declined)

    return DashboardSummary(
        total_patients=len(insights),
        high_risk_count=high,
        worsening_count=worsening,
        care_path_variance_count=variance_count,
        pending_investigations=pending_inv,
        cohort_distribution=cohort_counts,
        conversion_funnel=ConversionFunnelSummary(
            total_advised=funnel_total,
            contacted=funnel_contacted,
            interested=funnel_interested,
            converted=funnel_converted,
            declined=funnel_declined,
            pending=funnel_pending,
        ),
    )
