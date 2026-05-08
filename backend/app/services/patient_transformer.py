"""Patient data transformation utilities for the Cohere pipeline.

Responsible for:
- Simplifying raw patient JSON into a compact LLM-friendly payload
- Extracting a flat PatientInsight dict from whatever Cohere returns
- Normalizing Cohere's response fields to pass Pydantic validation
"""

from datetime import datetime
from typing import Any, Dict, List, Optional


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
            vitals = v.get("vitals", {})
            labs = v.get("labs", {})
            key_labs = {
                k: labs[k]
                for k in ["hba1c", "creatinine", "ldl", "hemoglobin", "uric_acid"]
                if k in labs
            }
            visit_summary.append({
                "date": v.get("visit_date"),
                "complaint": v.get("chief_complaint"),
                "bp": vitals.get("bp"),
                "hr": vitals.get("hr"),
                "spo2": vitals.get("spo2"),
                "key_labs": key_labs if key_labs else None,
                "diagnosis": v.get("diagnosis"),
            })

        call_summary = [
            {
                "date": c.get("call_date"),
                "outcome": c.get("call_status"),
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


def normalize_patient_data(data: dict, simplified: dict) -> dict:
    """Normalize Cohere response fields to pass Pydantic validation.

    - Always overwrites identity fields from the known source data.
    - Maps non-standard enum strings to valid values.
    """
    # Identity fields — always take from trusted source, not the LLM.
    # We use explicit type coercion to guard against Cohere returning null for these.
    data["patient_id"] = simplified.get("id") or data.get("patient_id") or "UNKNOWN"
    data["patient_name"] = str(simplified.get("name") or data.get("patient_name") or "Unknown Patient")
    # age: cast to int safely; Cohere sometimes emits null even when we sent the age
    raw_age = simplified.get("age") or data.get("age")
    try:
        data["age"] = int(raw_age) if raw_age is not None else 0
    except (TypeError, ValueError):
        data["age"] = 0
    data["gender"] = str(simplified.get("gender") or data.get("gender") or "Unknown")

    # Progression status
    prog = str(data.get("progression_status", "stable")).lower()
    if prog not in _VALID_PROG:
        data["progression_status"] = _PROG_MAP.get(prog, "stable")

    # progression_metrics trend values
    for metric in data.get("progression_metrics", []):
        trend = str(metric.get("trend", "stable")).lower()
        if trend not in _VALID_PROG:
            metric["trend"] = _PROG_MAP.get(trend, "stable")

    # risk_level
    risk = str(data.get("risk_level", "medium")).lower()
    if risk not in {"high", "medium", "low"}:
        data["risk_level"] = "medium"

    # admission_status
    conv = data.get("conversion_status")
    if isinstance(conv, dict):
        status = str(conv.get("admission_status", "Pending"))
        if status not in {"Pending", "In Progress", "Declined", "Converted"}:
            conv["admission_status"] = "Pending"

    # Cohere sometimes returns `source` as a list instead of a single dict.
    # NextAction, RiskFlag, and ProgressionPoint all expect SourceTrace (not a list).
    # Fix: take the first element if a list is returned.
    def _coerce_source(obj: Any) -> None:
        """In-place: if obj['source'] is a list, replace with its first element (or empty dict)."""
        if not isinstance(obj, dict):
            return
        src = obj.get("source")
        if isinstance(src, list):
            obj["source"] = src[0] if src else {"type": "visit_note", "description": "", "visit_number": None}

    for action in data.get("next_actions", []):
        _coerce_source(action)

    for flag in data.get("risk_flags", []):
        _coerce_source(flag)

    for metric in data.get("progression_metrics", []):
        _coerce_source(metric)

    for variance_item in data.get("care_path_variance", {}).get("variances", []):
        # VarianceDetail.source is List[SourceTrace] so keep it as a list,
        # but ensure each element is a dict (not a nested list).
        src = variance_item.get("source")
        if isinstance(src, list):
            variance_item["source"] = [
                s if isinstance(s, dict) else {"type": "visit_note", "description": str(s), "visit_number": None}
                for s in src
            ]
        elif isinstance(src, dict):
            variance_item["source"] = [src]  # wrap single dict in list

    return data
