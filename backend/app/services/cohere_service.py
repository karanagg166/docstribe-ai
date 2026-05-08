import json
import logging
import cohere
from typing import List, Dict, Any

from app.config import settings
from app.models.schemas import (
    DashboardResponse, PatientInsight, DashboardSummary, CohortBucket, 
    RiskLevel, ProgressionStatus, CarePathVariance, ConversionStatus, 
    PendingActionsSummary, SourceTrace, NextAction, VisitSummary, RiskFlag
)
from datetime import datetime

logger = logging.getLogger(__name__)

# Initialize Cohere client conditionally
cohere_client = None
if settings.cohere_api_key:
    cohere_client = cohere.ClientV2(api_key=settings.cohere_api_key)

SYSTEM_PROMPT = """You are an expert clinical triage assistant analyzing OPD referral conversion data.
Your goal is to transform the raw patient list into structured insights, categorizing risk levels 
and determining the barriers to admission/conversion.

Analyze the provided list of patients and return a JSON object that EXACTLY matches this structure:
{
  "summary": {
    "total_patients": 0,
    "high_risk_count": 0,
    "worsening_count": 0,
    "care_path_variance_count": 0,
    "pending_investigations": 0,
    "cohort_distribution": {}
  },
  "patients": [
    {
      "patient_id": "string",
      "patient_name": "string",
      "age": 0,
      "gender": "string",
      "primary_condition": "string",
      "cohort_bucket": "General Follow-up",
      "risk_level": "high",
      "risk_reasoning": "string",
      "progression_status": "stable",
      "care_path_variance": {"detected": false, "variances": []},
      "clinical_summary": "string",
      "visit_timeline": [],
      "progression_metrics": [],
      "risk_flags": [],
      "next_actions": [],
      "conversion_status": {"procedure_advised": false, "admission_status": "Pending", "barrier": null, "barrier_detail": null, "source": []},
      "pending_actions_summary": {"pending_procedures": 0, "pending_labs": 0, "pending_referrals": 0},
      "suggested_priority_rank": 1,
      "last_visit_date": "2024-01-01",
      "days_since_last_visit": 0
    }
  ],
  "generated_at": "2024-01-01T00:00:00Z",
  "from_cache": false
}

RISK GUIDELINES:
- high: Abnormal vitals (e.g. BP > 160/100, HR > 100), severe symptoms, or "Urgent" admission advised.
- medium: Stable but chronic issues, "Elective" admission, seeking second opinions.
- low: Normal vitals, routine follow-ups, minor complaints.

VARIANCE GUIDELINES:
A "care path variance" occurs when a patient deviates from the recommended clinical workflow. Set "detected": true and list specific "variances" if:
- The patient has 3 or more "pending" actions (labs, procedures, referrals).
- The call logs indicate the patient declined treatment, is deferring due to cost/insurance, or is unreachable.
- The patient's symptoms are worsening despite prior interventions.

Do NOT include markdown formatting (like ```json), just return the raw JSON object.
"""

async def analyze_all_patients(patients: List[Dict[str, Any]]) -> DashboardResponse:
    """Analyze the entire patient list using Cohere to generate dashboard insights."""
    if not cohere_client:
        logger.warning("Cohere API key not configured. Returning dummy data.")
        return _generate_dummy_response(patients)
        
    try:
        # We need to serialize the patient data to send to the LLM
        # For large lists, we might need to truncate or send specific fields
        simplified_patients = _simplify_patient_data_for_llm(patients)
        
        response = cohere_client.chat(
            model="command-r-plus-08-2024",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(simplified_patients)}
            ],
            response_format={"type": "json_object"}
        )
        
        # Parse the JSON response
        response_text = response.message.content[0].text
        # Clean up in case the LLM ignored instructions and added markdown
        if response_text.startswith("```json"):
            response_text = response_text[7:-3]
        elif response_text.startswith("```"):
            response_text = response_text[3:-3]
            
        parsed_data = json.loads(response_text)
        
        # Validate against our Pydantic schema
        return DashboardResponse(**parsed_data)
        
    except Exception as e:
        logger.error(f"Error during Cohere analysis: {e}")
        # Fallback to deterministic logic if LLM fails
        return _generate_dummy_response(patients)

def _simplify_patient_data_for_llm(patients: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reduce the payload size by only sending relevant fields to the LLM."""
    simplified = []
    for p in patients:
        clinical = p.get("clinical_data", {})
        latest_visit = clinical.get("latest_visit", {})
        opd = p.get("opd_details", {})
        
        simplified.append({
            "id": p.get("patient_id"),
            "name": p.get("personal_info", {}).get("name"),
            "age": p.get("personal_info", {}).get("age"),
            "gender": p.get("personal_info", {}).get("gender"),
            "vitals": latest_visit.get("vitals", {}),
            "diagnosis": latest_visit.get("diagnosis"),
            "urgency": opd.get("admission_advised", {}).get("urgency"),
            "latest_call_notes": _get_latest_call_notes(p.get("conversion_tracking", {}).get("call_logs", []))
        })
    return simplified

def _get_latest_call_notes(logs: List[Dict[str, Any]]) -> str:
    if not logs:
        return "No contact"
    # Assuming logs are sorted, or we just grab the last one
    latest = logs[-1]
    return f"{latest.get('status', '')}: {latest.get('notes', '')}"

def _generate_dummy_response(patients: List[Dict[str, Any]]) -> DashboardResponse:
    """Fallback generator if Cohere isn't available or fails.
    Produces deterministic insights from the raw patient JSON data."""
    insights = []
    high = med = low = 0
    worsening = 0
    variance_count = 0
    pending_inv = 0
    cohort_counts: Dict[str, int] = {}
    
    for idx, p in enumerate(patients):
        # Extract fields from the raw JSON structure
        patient_id = p.get("patient_id", f"P-{idx+1:04d}")
        patient_name = p.get("name", "Unknown Patient")
        age = p.get("age", 0)
        gender = p.get("gender", "Unknown")
        
        # Determine primary condition from referral or history
        referral = p.get("current_referral", {})
        history = p.get("history", {})
        known_conditions = history.get("known_conditions", [])
        presenting = history.get("presenting_complaints", [])
        primary_condition = presenting[0]["condition"] if presenting else (known_conditions[0] if known_conditions else "General Follow-up")
        
        # Determine cohort from department/condition
        dept = referral.get("department", "")
        cohort = _determine_cohort(dept, known_conditions, primary_condition)
        cohort_counts[cohort] = cohort_counts.get(cohort, 0) + 1
        
        # Determine risk level from vitals and urgency
        visit_history = p.get("visit_history", [])
        risk = _determine_risk(visit_history, referral)
        if risk == RiskLevel.HIGH:
            high += 1
        elif risk == RiskLevel.MEDIUM:
            med += 1
        else:
            low += 1
        
        # Build visit timeline
        timeline = []
        for v_idx, visit in enumerate(visit_history):
            timeline.append(VisitSummary(
                visit_number=v_idx + 1,
                date=visit.get("visit_date", ""),
                chief_complaint=visit.get("chief_complaint", ""),
                doctor_note=visit.get("examination", ""),
                medications_prescribed=visit.get("prescription", []),
                labs_ordered=list(visit.get("labs", {}).keys()) if visit.get("labs") else [],
                vitals=visit.get("vitals"),
            ))
        
        # Build risk flags from latest vitals
        risk_flags = _extract_risk_flags(visit_history)
        
        # Determine progression
        progression = _determine_progression(visit_history)
        if progression == ProgressionStatus.WORSENING:
            worsening += 1
        
        # Determine conversion status from call history
        call_history = p.get("call_history", [])
        conversion = _determine_conversion(call_history, referral)
        
        # Count pending actions
        advised = p.get("advised_actions", [])
        pending_procs = sum(1 for a in advised if a.get("action_type") == "procedure" and a.get("status") == "pending")
        pending_labs = sum(1 for a in advised if a.get("action_type") in ("lab", "radiology_test") and a.get("status") == "pending")
        pending_refs = sum(1 for a in advised if a.get("action_type") == "referral" and a.get("status") == "pending")
        pending_inv += pending_procs + pending_labs
        
        # Build next actions from advised_actions
        next_actions = []
        for a in advised[:3]:
            next_actions.append(NextAction(
                action=a.get("title", "Follow up"),
                reason=a.get("description", "As advised"),
                priority=1 if a.get("action_type") == "procedure" else 2,
                action_type=a.get("action_type", "follow_up"),
                source=SourceTrace(type="visit_note", description=a.get("description", "From clinical record"), visit_number=len(visit_history))
            ))
        if not next_actions:
            next_actions.append(NextAction(action="Follow up", reason="Routine check", priority=3, action_type="follow_up",
                                           source=SourceTrace(type="visit_note", description="Scheduled follow-up", visit_number=1)))
        
        # Clinical summary
        summary_text = referral.get("op_advised_reason", f"{patient_name}, {age}y {gender}, presenting with {primary_condition}.")
        
        # Last visit
        last_visit = visit_history[-1].get("visit_date", "2024-01-01") if visit_history else "2024-01-01"
        
        # Detect care path variances
        has_variance = _detect_variance(advised, call_history)
        if has_variance:
            variance_count += 1
        
        insights.append(PatientInsight(
            patient_id=patient_id,
            patient_name=patient_name,
            age=age,
            gender=gender,
            primary_condition=primary_condition.title(),
            cohort_bucket=cohort,
            risk_level=risk,
            risk_reasoning=_get_risk_reasoning(risk, visit_history, referral),
            progression_status=progression,
            care_path_variance=CarePathVariance(detected=has_variance, variances=[]),
            clinical_summary=summary_text,
            visit_timeline=timeline,
            progression_metrics=[],
            risk_flags=risk_flags,
            next_actions=next_actions,
            conversion_status=conversion,
            pending_actions_summary=PendingActionsSummary(
                pending_procedures=pending_procs,
                pending_labs=pending_labs,
                pending_referrals=pending_refs
            ),
            suggested_priority_rank=idx + 1,
            last_visit_date=last_visit,
            days_since_last_visit=_days_since(last_visit)
        ))
    
    # Sort by risk (high first)
    risk_order = {RiskLevel.HIGH: 0, RiskLevel.MEDIUM: 1, RiskLevel.LOW: 2}
    insights.sort(key=lambda x: risk_order.get(x.risk_level, 1))
    for rank, ins in enumerate(insights):
        ins.suggested_priority_rank = rank + 1
        
    summary = DashboardSummary(
        total_patients=len(patients),
        high_risk_count=high,
        worsening_count=worsening,
        care_path_variance_count=variance_count,
        pending_investigations=pending_inv,
        cohort_distribution=cohort_counts
    )
    
    return DashboardResponse(
        summary=summary,
        patients=insights,
        generated_at=datetime.utcnow(),
        from_cache=False
    )


# ─── Helper functions for deterministic fallback ────────────

def _determine_cohort(dept: str, conditions: list, primary: str) -> str:
    dept_lower = dept.lower()
    conditions_str = " ".join(c.lower() for c in conditions)
    primary_lower = primary.lower()
    
    if "cardiol" in dept_lower or "angina" in primary_lower or "cardiac" in conditions_str:
        return CohortBucket.CARDIAC_INTERVENTION_PENDING
    elif "diabet" in conditions_str or "hba1c" in primary_lower:
        return CohortBucket.POORLY_CONTROLLED_DIABETIC
    elif "hypertension" in conditions_str or "htn" in conditions_str:
        return CohortBucket.HTN_FOLLOWUP
    elif "ckd" in conditions_str or "kidney" in conditions_str or "renal" in conditions_str:
        return CohortBucket.CKD_FOLLOWUP
    elif "neuro" in dept_lower or "dystonia" in primary_lower or "headache" in primary_lower or "migrain" in primary_lower:
        return CohortBucket.NEUROLOGICAL_DISORDER
    elif "ortho" in dept_lower or "arthro" in primary_lower or "knee" in primary_lower or "shoulder" in primary_lower:
        return CohortBucket.MUSCULOSKELETAL_SURGICAL
    elif "gastro" in dept_lower or "gi" in primary_lower or "liver" in conditions_str or "hepat" in conditions_str:
        return CohortBucket.GI_HEPATOBILIARY
    elif len(conditions) >= 3:
        return CohortBucket.HIGH_RISK_MULTIMORBID
    elif "post" in primary_lower and "procedure" in primary_lower:
        return CohortBucket.POST_PROCEDURE
    else:
        return CohortBucket.GENERAL_FOLLOWUP

def _determine_risk(visit_history: list, referral: dict) -> RiskLevel:
    """Determine risk from latest vitals and urgency."""
    if not visit_history:
        return RiskLevel.MEDIUM
    
    latest = visit_history[-1]
    vitals = latest.get("vitals", {})
    
    # Check BP
    bp = vitals.get("bp", "")
    if bp:
        parts = bp.replace("/", " ").split()
        try:
            systolic = int(parts[0])
            if systolic > 160:
                return RiskLevel.HIGH
        except (ValueError, IndexError):
            pass
    
    # Check HR
    hr = vitals.get("hr", 0)
    if isinstance(hr, (int, float)) and hr > 100:
        return RiskLevel.HIGH
    
    # Check urgency
    urgency = referral.get("op_advised_reason", "").lower()
    if "urgent" in urgency or "status migrain" in urgency or "severe" in urgency:
        return RiskLevel.HIGH
    
    # If we have multiple known conditions
    if (referral.get("estimated_los_days") or 0) >= 5:
        return RiskLevel.MEDIUM
    
    return RiskLevel.MEDIUM

def _determine_progression(visit_history: list) -> ProgressionStatus:
    if len(visit_history) < 2:
        return ProgressionStatus.STABLE
    
    latest = visit_history[-1]
    prev = visit_history[-2]
    
    # Compare chief complaints for worsening keywords
    chief = latest.get("chief_complaint", "").lower()
    if any(w in chief for w in ["worsening", "increasing", "persistent", "severe", "continuous"]):
        return ProgressionStatus.WORSENING
    if any(w in chief for w in ["improving", "better", "decreased", "resolved"]):
        return ProgressionStatus.IMPROVING
    if any(w in chief for w in ["recurrent", "recurring", "again"]):
        return ProgressionStatus.RECURRING
    
    return ProgressionStatus.STABLE

def _extract_risk_flags(visit_history: list) -> List[RiskFlag]:
    flags = []
    if not visit_history:
        return flags
    
    latest = visit_history[-1]
    vitals = latest.get("vitals", {})
    labs = latest.get("labs", {})
    
    # BP check
    bp = vitals.get("bp", "")
    if bp:
        parts = bp.replace("/", " ").split()
        try:
            systolic = int(parts[0])
            if systolic > 150:
                flags.append(RiskFlag(
                    flag=f"Elevated BP: {bp}",
                    detail=f"Systolic {systolic} mmHg above safe threshold",
                    severity=RiskLevel.HIGH if systolic > 160 else RiskLevel.MEDIUM,
                    source=SourceTrace(type="vital", description=f"BP: {bp}", visit_number=len(visit_history))
                ))
        except (ValueError, IndexError):
            pass
    
    # HbA1c check
    hba1c = labs.get("hba1c", 0)
    if isinstance(hba1c, (int, float)) and hba1c > 7.0:
        flags.append(RiskFlag(
            flag=f"HbA1c elevated: {hba1c}",
            detail=f"HbA1c {hba1c}% — above target threshold of 7.0%",
            severity=RiskLevel.HIGH if hba1c > 8.0 else RiskLevel.MEDIUM,
            source=SourceTrace(type="lab", description=f"HbA1c: {hba1c}%", visit_number=len(visit_history))
        ))
    
    # Creatinine check
    creatinine = labs.get("creatinine", 0)
    if isinstance(creatinine, (int, float)) and creatinine > 1.2:
        flags.append(RiskFlag(
            flag=f"Creatinine elevated: {creatinine}",
            detail=f"Creatinine {creatinine} mg/dL — suggests renal concern",
            severity=RiskLevel.MEDIUM,
            source=SourceTrace(type="lab", description=f"Creatinine: {creatinine}", visit_number=len(visit_history))
        ))
    
    return flags

def _determine_conversion(call_history: list, referral: dict) -> ConversionStatus:
    procedure_advised = referral.get("op_advised", False)
    
    if not call_history:
        return ConversionStatus(procedure_advised=procedure_advised, admission_status="Pending", source=[])
    
    latest_call = call_history[-1]
    transcript = latest_call.get("transcript_summary", "").lower()
    
    if any(w in transcript for w in ["declined", "not interested", "refuses", "declined admission"]):
        barrier = "Patient declined"
        detail = latest_call.get("transcript_summary", "")
        return ConversionStatus(
            procedure_advised=procedure_advised, admission_status="Declined",
            barrier=barrier, barrier_detail=detail,
            source=[SourceTrace(type="visit_note", description=detail[:100], visit_number=0)]
        )
    elif any(w in transcript for w in ["insurance", "cost", "funds", "afford"]):
        return ConversionStatus(
            procedure_advised=procedure_advised, admission_status="Pending",
            barrier="Financial/Insurance barrier",
            barrier_detail=latest_call.get("transcript_summary", ""),
            source=[SourceTrace(type="visit_note", description="Financial concern noted", visit_number=0)]
        )
    elif any(w in transcript for w in ["delay", "wait", "later", "managing", "physiotherapy"]):
        return ConversionStatus(
            procedure_advised=procedure_advised, admission_status="Pending",
            barrier="Patient deferring",
            barrier_detail=latest_call.get("transcript_summary", ""),
            source=[SourceTrace(type="visit_note", description="Patient wants to wait", visit_number=0)]
        )
    elif any(w in transcript for w in ["interested", "agree", "ready", "proceed"]):
        return ConversionStatus(procedure_advised=procedure_advised, admission_status="In Progress", source=[])
    
    return ConversionStatus(procedure_advised=procedure_advised, admission_status="Pending", source=[])

def _detect_variance(advised: list, call_history: list) -> bool:
    """Detect if there are pending actions overdue or barriers."""
    pending_count = sum(1 for a in advised if a.get("status") == "pending")
    has_barrier = any(
        any(w in c.get("transcript_summary", "").lower() for w in ["declined", "not interested", "insurance", "cost"])
        for c in call_history
    )
    return pending_count > 2 or has_barrier

def _get_risk_reasoning(risk: RiskLevel, visit_history: list, referral: dict) -> str:
    if risk == RiskLevel.HIGH:
        return f"Patient flagged high-risk based on vitals and clinical urgency. {referral.get('department', '')} referral with estimated {referral.get('estimated_los_days', 0)}-day stay."
    elif risk == RiskLevel.MEDIUM:
        return f"Moderate risk patient under {referral.get('department', 'specialist')} care with ongoing monitoring."
    return "Low risk — routine follow-up, stable vitals."

def _days_since(date_str: str) -> int:
    try:
        visit_date = datetime.strptime(date_str, "%Y-%m-%d")
        return (datetime.utcnow() - visit_date).days
    except (ValueError, TypeError):
        return 0
