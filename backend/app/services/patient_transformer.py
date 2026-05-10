"""Patient data transformation utilities for the Cohere pipeline.

Responsible for:
- Simplifying raw patient JSON into a compact LLM-friendly payload
- Extracting a flat PatientInsight dict from whatever Cohere returns
- Normalizing Cohere's response fields to pass Pydantic validation
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# Valid cohort bucket values (must match CohortBucket enum)
_VALID_COHORTS = {
    "Cardiac Intervention Pending",
    "Poorly Controlled Diabetic",
    "Hypertension Follow-up",
    "CKD Follow-up",
    "Neurological/Movement Disorder",
    "Recurrent Infection",
    "Post-Procedure Recovery",
    "High Utilization OPD",
    "General Follow-up",
    "Musculoskeletal/Surgical",
    "GI/Hepatobiliary",
    "High-Risk Multi-Morbid",
}

# Fuzzy mapping for common LLM misspellings / variations
_COHORT_FUZZY_MAP: Dict[str, str] = {
    "cardiac": "Cardiac Intervention Pending",
    "diabetic": "Poorly Controlled Diabetic",
    "diabetes": "Poorly Controlled Diabetic",
    "hypertension": "Hypertension Follow-up",
    "htn": "Hypertension Follow-up",
    "ckd": "CKD Follow-up",
    "kidney": "CKD Follow-up",
    "renal": "CKD Follow-up",
    "neuro": "Neurological/Movement Disorder",
    "movement": "Neurological/Movement Disorder",
    "dystonia": "Neurological/Movement Disorder",
    "parkinson": "Neurological/Movement Disorder",
    "ortho": "Musculoskeletal/Surgical",
    "musculoskeletal": "Musculoskeletal/Surgical",
    "surgical": "Musculoskeletal/Surgical",
    "joint": "Musculoskeletal/Surgical",
    "gi": "GI/Hepatobiliary",
    "hepat": "GI/Hepatobiliary",
    "liver": "GI/Hepatobiliary",
    "gastro": "GI/Hepatobiliary",
    "infection": "Recurrent Infection",
    "post-op": "Post-Procedure Recovery",
    "recovery": "Post-Procedure Recovery",
    "multi-morbid": "High-Risk Multi-Morbid",
    "multimorbid": "High-Risk Multi-Morbid",
}


def simplify_patients(patients: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build a compact but COMPLETE patient payload for Cohere.

    Includes full visit history, all advised actions, and full call history
    so that Cohere can accurately compute variance, trend, and conversion.
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    result = []

    for p in patients:
        personal = p.get("personal_info", {})
        history = p.get("history", {})
        referral = p.get("current_referral", {})
        opd = p.get("opd_details", {})
        visit_history = p.get("visit_history", [])
        call_history = p.get("call_history", [])
        advised = p.get("advised_actions", [])

        visit_summary = []
        for v in visit_history:
            vitals = v.get("vitals") or {}
            labs = v.get("labs") or {}
            prescription = v.get("prescription") or []
            imaging = v.get("imaging")
            # Include all available labs, not just a subset
            visit_summary.append({
                "date": v.get("visit_date"),
                "complaint": v.get("chief_complaint") or "Not recorded",
                "examination": v.get("examination"),
                "bp": vitals.get("bp"),
                "hr": vitals.get("hr"),
                "spo2": vitals.get("spo2"),
                "temp_f": vitals.get("temp_f"),
                "weight_kg": vitals.get("weight_kg"),
                "labs": labs if labs else None,
                "imaging": imaging,
                "diagnosis": v.get("diagnosis_text") or v.get("diagnosis") or "Pending",
                "prescription": prescription,
                "advice": v.get("advice"),
            })

        call_summary = [
            {
                "date": c.get("call_date"),
                "outcome": c.get("outcome") or c.get("call_status"),
                "duration_sec": c.get("duration_sec"),
                "summary": c.get("transcript_summary"),
            }
            for c in call_history
        ]

        advised_summary = [
            {
                "type": a.get("action_type"),
                "title": a.get("title"),
                "due": a.get("due_date"),
                "status": a.get("status"),
            }
            for a in advised
        ]

        result.append({
            "id": p.get("patient_id"),
            # Fields are top-level in this schema; fall back to personal_info for compat
            "name": p.get("name") or personal.get("name"),
            "age": p.get("age") or personal.get("age"),
            "gender": p.get("gender") or personal.get("gender"),
            "known_conditions": history.get("known_conditions", []),
            "presenting_complaints": [
                c.get("condition") for c in history.get("presenting_complaints", [])
            ],
            "department": referral.get("department"),
            "urgency_reason": (
                opd.get("admission_advised", {}).get("reason")
                or referral.get("op_advised_reason")
            ),
            "op_advised": referral.get("op_advised", False),
            "estimated_los_days": referral.get("estimated_los_days"),
            "today": today,
            "visit_summary": visit_summary,
            "advised_actions": advised_summary,
            "call_history": call_summary,
        })

    return result


def extract_patient_data(parsed: dict) -> dict:
    """Extract a flat PatientInsight dict from whatever structure Cohere returns.

    Handles:
    - {"patient": {...}}              ← Cohere single-patient format (most common)
    - {"patients": [{...}]}           ← Cohere sometimes wraps in array
    - {"patient_id": ..., ...}        ← Flat dict at top level
    - {someKey: {"patient_id": ...}}  ← Nested under an arbitrary key
    """
    if "patient" in parsed and isinstance(parsed["patient"], dict):
        return parsed["patient"]
    if "patients" in parsed and isinstance(parsed["patients"], list) and parsed["patients"]:
        return parsed["patients"][0]
    if "patient_id" in parsed:
        return parsed
    for v in parsed.values():
        if isinstance(v, dict) and "patient_id" in v:
            return v
    return parsed


# Maps non-standard progression/trend strings to valid enum values
_PROG_MAP: Dict[str, str] = {
    "rising": "worsening",
    "deteriorating": "worsening",
    "getting worse": "worsening",
    "getting better": "improving",
    "recovering": "improving",
    "resolved": "improving",
    "unchanged": "stable",
    "no change": "stable",
    "recurrent": "recurring",
    "relapsing": "recurring",
}
_VALID_PROG = {"worsening", "improving", "stable", "recurring"}


def _normalize_cohort_bucket(value: Any) -> str:
    """Map an LLM-returned cohort bucket to a valid CohortBucket enum value."""
    if not value or not isinstance(value, str):
        return "General Follow-up"
    
    # Direct match
    if value in _VALID_COHORTS:
        return value
    
    # Case-insensitive match
    lower = value.lower().strip()
    for valid in _VALID_COHORTS:
        if valid.lower() == lower:
            return valid
    
    # Fuzzy match via keywords
    for keyword, bucket in _COHORT_FUZZY_MAP.items():
        if keyword in lower:
            return bucket
    
    logger.warning(f"Unknown cohort bucket '{value}', defaulting to 'General Follow-up'")
    return "General Follow-up"


def _ensure_source(obj: Any) -> None:
    """In-place: ensure obj['source'] is a valid dict, not null or empty."""
    if not isinstance(obj, dict):
        return
    src = obj.get("source")
    if src is None or src == "":
        obj["source"] = {"type": "visit_note", "description": "Auto-generated", "visit_number": 0}
    elif isinstance(src, list):
        obj["source"] = src[0] if src else {"type": "visit_note", "description": "Auto-generated", "visit_number": 0}


def _safe_int(value: Any, default: int = 0) -> int:
    """Safely cast a value to int."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_patient_data(data: dict, simplified: dict) -> dict:
    """Normalize Cohere response fields to pass Pydantic validation.

    - Always overwrites identity fields from the known source data.
    - Maps non-standard enum strings to valid values.
    - Handles known LLM failure modes (wrong types, null sources, etc.)
    """
    # Identity fields — always take from trusted source, not the LLM.
    data["patient_id"] = simplified.get("id") or data.get("patient_id") or "UNKNOWN"
    data["patient_name"] = str(simplified.get("name") or data.get("patient_name") or "Unknown Patient")
    data["age"] = _safe_int(simplified.get("age") or data.get("age"))
    data["gender"] = str(simplified.get("gender") or data.get("gender") or "Unknown")

    # Integer type coercion
    data["suggested_priority_rank"] = _safe_int(data.get("suggested_priority_rank"), 99)
    data["days_since_last_visit"] = _safe_int(data.get("days_since_last_visit"))

    # Progression status
    prog = str(data.get("progression_status", "stable")).lower()
    if prog not in _VALID_PROG:
        data["progression_status"] = _PROG_MAP.get(prog, "stable")

    # progression_metrics — handle wrong types
    metrics = data.get("progression_metrics", [])
    if isinstance(metrics, str):
        metrics = []
        data["progression_metrics"] = metrics
    if not isinstance(metrics, list):
        data["progression_metrics"] = []
        metrics = []
    
    for metric in metrics:
        if not isinstance(metric, dict):
            continue
        trend = str(metric.get("trend", "stable")).lower()
        if trend not in _VALID_PROG:
            metric["trend"] = _PROG_MAP.get(trend, "stable")
        
        # Handle values returned as dict instead of list
        values = metric.get("values", [])
        if isinstance(values, dict):
            # Convert {"Jan": "8.2", "Apr": "7.6"} to [{"date": "Jan", "value": "8.2"}, ...]
            metric["values"] = [{"date": k, "value": str(v)} for k, v in values.items()]
        elif not isinstance(values, list):
            metric["values"] = []
        
        _ensure_source(metric)

    # risk_level
    risk = str(data.get("risk_level", "medium")).lower()
    if risk not in {"high", "medium", "low"}:
        data["risk_level"] = "medium"

    # cohort_bucket normalization
    data["cohort_bucket"] = _normalize_cohort_bucket(data.get("cohort_bucket"))

    # admission_status
    conv = data.get("conversion_status")
    if isinstance(conv, dict):
        status = str(conv.get("admission_status", "Pending"))
        if status not in {"Pending", "In Progress", "Declined", "Converted"}:
            conv["admission_status"] = "Pending"
        # Ensure source is a list for ConversionStatus
        src = conv.get("source")
        if src is None:
            conv["source"] = []
        elif isinstance(src, dict):
            conv["source"] = [src]
    elif conv is None:
        data["conversion_status"] = {
            "procedure_advised": simplified.get("op_advised", False),
            "admission_status": "Pending",
            "barrier": None,
            "barrier_detail": None,
            "source": []
        }

    # pending_actions_summary — ensure it exists and has int values
    pas = data.get("pending_actions_summary")
    if not isinstance(pas, dict):
        data["pending_actions_summary"] = {"pending_procedures": 0, "pending_labs": 0, "pending_referrals": 0}
    else:
        pas["pending_procedures"] = _safe_int(pas.get("pending_procedures"))
        pas["pending_labs"] = _safe_int(pas.get("pending_labs"))
        pas["pending_referrals"] = _safe_int(pas.get("pending_referrals"))

    # risk_flags — handle string instead of list
    risk_flags = data.get("risk_flags", [])
    if isinstance(risk_flags, str):
        data["risk_flags"] = [{"flag": risk_flags, "detail": risk_flags, "severity": "medium",
                               "source": {"type": "visit_note", "description": "Auto-generated", "visit_number": 0}}]
        risk_flags = data["risk_flags"]
    if not isinstance(risk_flags, list):
        data["risk_flags"] = []
        risk_flags = []
    
    for flag in risk_flags:
        _ensure_source(flag)

    # next_actions — handle string instead of list
    next_actions = data.get("next_actions", [])
    if isinstance(next_actions, str):
        data["next_actions"] = [{"action": next_actions, "reason": "", "priority": 1,
                                 "action_type": "clinical",
                                 "source": {"type": "visit_note", "description": "Auto-generated", "visit_number": 0}}]
        next_actions = data["next_actions"]
    if not isinstance(next_actions, list):
        data["next_actions"] = []
        next_actions = []
    
    for action in next_actions:
        _ensure_source(action)
        action["priority"] = _safe_int(action.get("priority"), 1)

    # care_path_variance — ensure proper structure
    cpv = data.get("care_path_variance")
    if not isinstance(cpv, dict):
        data["care_path_variance"] = {"detected": False, "variances": []}
    else:
        for variance_item in cpv.get("variances", []):
            # VarianceDetail.source is List[SourceTrace] so keep it as a list
            src = variance_item.get("source")
            if isinstance(src, list):
                variance_item["source"] = [
                    s if isinstance(s, dict) else {"type": "visit_note", "description": str(s), "visit_number": None}
                    for s in src
                ]
            elif isinstance(src, dict):
                variance_item["source"] = [src]  # wrap single dict in list
            elif src is None:
                variance_item["source"] = [{"type": "visit_note", "description": "Auto-generated", "visit_number": 0}]

    # visit_timeline — ensure it exists
    if not isinstance(data.get("visit_timeline"), list):
        data["visit_timeline"] = []
    for vt in data.get("visit_timeline", []):
        if isinstance(vt, dict):
            vt["visit_number"] = _safe_int(vt.get("visit_number"), 1)

    # clinical_summary — ensure it exists
    if not data.get("clinical_summary"):
        data["clinical_summary"] = data.get("risk_reasoning", "No clinical summary available.")

    # primary_condition — ensure it exists
    if not data.get("primary_condition"):
        complaints = simplified.get("presenting_complaints", [])
        data["primary_condition"] = complaints[0] if complaints else "Unspecified"

    # last_visit_date — ensure it exists
    if not data.get("last_visit_date"):
        visits = simplified.get("visit_summary", [])
        if visits:
            data["last_visit_date"] = visits[-1].get("date", simplified.get("today", ""))
        else:
            data["last_visit_date"] = simplified.get("today", datetime.utcnow().strftime("%Y-%m-%d"))

    # risk_reasoning — ensure it exists
    if not data.get("risk_reasoning"):
        data["risk_reasoning"] = "Risk level determined by clinical assessment."

    return data
