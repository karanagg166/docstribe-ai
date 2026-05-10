from app.models.schemas import CarePathVariance, VarianceDetail, SourceTrace
from app.services.clinical_rules import (
    CONVERSION_DECLINED_KEYWORDS,
    CONVERSION_FINANCIAL_KEYWORDS,
    CONVERSION_DEFERRING_KEYWORDS,
    LAB_THRESHOLDS,
    match_cohort
)
from typing import List
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

def detect_variances(patient: dict) -> CarePathVariance:
    """
    Rule-based variance detection as validation layer.
    
    Detects clinical care path variances only (NOT financial/conversion barriers):
    1. Overdue advised actions (due_date in the past, status still "pending")
    2. Multiple pending actions (2+ pending)
    3. Call log: patient declined treatment
    4. Call log: patient unreachable (2+ no_answer)
    5. Lab trend crossing threshold delta
    6. Follow-up gap > 6 months for chronic cohorts
    7. Missing baseline labs for chronic cohorts
    8. Medication escalation (multiple new meds with no follow-up)
    """
    variances: List[VarianceDetail] = []
    today = date.today()
    visit_history = patient.get("visit_summary", [])
    if not visit_history:
        # Fallback to older format if needed
        visit_history = patient.get("visit_history", patient.get("visits", []))
    
    # --- 1 & 2: Check advised_actions ---
    advised_actions = patient.get("advised_actions", [])
    pending_actions = [a for a in advised_actions if str(a.get("status", "")).lower() == "pending"]
    overdue_actions = []
    
    for action in pending_actions:
        due_date_str = action.get("due", action.get("due_date", ""))
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                if due_date < today:
                    overdue_actions.append(action)
            except (ValueError, TypeError):
                pass
    
    # Overdue actions variance
    if overdue_actions:
        for action in overdue_actions:
            variances.append(VarianceDetail(
                description=f"Overdue: {action.get('title', 'Action')} was due {action.get('due', action.get('due_date', 'unknown'))}",
                expected_action=f"Complete {action.get('type', action.get('action_type', 'action'))}: {action.get('title', '')}",
                actual_finding=f"Status is still 'pending' past due date",
                source=[SourceTrace(
                    type="visit_note",
                    description=f"Advised action: {action.get('title', '')}",
                    visit_number=len(visit_history)
                )]
            ))
    
    # Multiple pending actions variance
    if len(pending_actions) >= 2 and not overdue_actions:
        variances.append(VarianceDetail(
            description=f"{len(pending_actions)} advised actions are still pending",
            expected_action="Completion or scheduling of advised procedures/labs/referrals",
            actual_finding=f"Pending: {', '.join(a.get('title', '') for a in pending_actions[:3])}",
            source=[SourceTrace(
                type="visit_note",
                description="Multiple pending advised actions",
                visit_number=len(visit_history)
            )]
        ))
    
    # --- 3-6: Check call_history ---
    call_history = patient.get("call_history", [])
    no_answer_count = 0
    
    for call in call_history:
        outcome = str(call.get("outcome", "")).lower()
        summary = str(call.get("summary", call.get("transcript_summary", ""))).lower()
        call_date = call.get("date", call.get("call_date", ""))
        
        # Track no-answers
        if outcome in ["no_answer", "no answer", "not_connected", "switched_off"]:
            no_answer_count += 1
            continue
        
        # Decline detection — exclude financial/insurance/deferral reasons
        if any(kw in summary for kw in CONVERSION_DECLINED_KEYWORDS):
            is_financial_or_deferral = any(
                fkw in summary for fkw in CONVERSION_FINANCIAL_KEYWORDS + CONVERSION_DEFERRING_KEYWORDS
            )
            if not is_financial_or_deferral:
                variances.append(VarianceDetail(
                    description="Patient declined treatment/admission",
                    expected_action="Patient acceptance of advised procedure/admission",
                    actual_finding=f"Call on {call_date}: Patient expressed refusal or disinterest",
                    source=[SourceTrace(
                        type="visit_note",
                        description=f"Call log: {summary[:100]}",
                        visit_number=len(visit_history)
                    )]
                ))
        
        # NOTE: Financial/insurance barriers and patient deferral are tracked
        # via conversion_status, NOT as clinical variances.
    
    # Unreachable patient (2+ no_answer)
    if no_answer_count >= 2:
        variances.append(VarianceDetail(
            description=f"Patient unreachable ({no_answer_count} failed contact attempts)",
            expected_action="Successful patient contact for follow-up coordination",
            actual_finding=f"{no_answer_count} call attempts resulted in no answer",
            source=[SourceTrace(
                type="visit_note",
                description="Multiple failed contact attempts",
                visit_number=len(visit_history)
            )]
        ))

    # Determine cohort if needed for chronic disease logic
    cohort = patient.get("cohort")
    if not cohort:
        # Best effort to guess cohort based on simplified data
        department = (patient.get("department") or "").lower()
        conditions = " ".join(patient.get("known_conditions", [])).lower()
        primary = " ".join(patient.get("presenting_complaints", [])).lower()
        cohort = match_cohort(department, conditions, primary, len(patient.get("known_conditions", [])))

    chronic_cohorts = ["Poorly Controlled Diabetic", "Hypertension Follow-up", "CKD Follow-up"]

    # --- 7. Lab Trend Variance ---
    # Extract points for each lab
    for lab_key, cfg in LAB_THRESHOLDS.items():
        points = []
        for v_idx, v in enumerate(visit_history):
            labs = v.get("labs") or {}
            val = labs.get(lab_key)
            if isinstance(val, (int, float)):
                points.append(float(val))
        
        if len(points) >= 2:
            delta = cfg.get("delta", 0.2)
            direction = cfg.get("direction", "high_is_bad")
            display = cfg.get("display_name", lab_key.replace("_", " ").title())
            first, last = points[0], points[-1]
            
            worsening = False
            if direction == "high_is_bad" and last > first + delta:
                worsening = True
            elif direction == "low_is_bad" and last < first - delta:
                worsening = True
                
            if worsening:
                variances.append(VarianceDetail(
                    description=f"{display} is trending worse across visits",
                    expected_action=f"Stabilization or improvement of {display}",
                    actual_finding=f"{display} changed from {first} to {last} (Delta > {delta})",
                    source=[SourceTrace(
                        type="lab",
                        description=f"{display} trend worsening",
                        visit_number=len(visit_history)
                    )]
                ))

    # --- 8. Follow-up gap > 6 months for chronic cohorts ---
    if cohort in chronic_cohorts and len(visit_history) > 0:
        last_visit_str = visit_history[-1].get("date", visit_history[-1].get("visit_date", ""))
        if last_visit_str:
            try:
                last_visit = datetime.strptime(last_visit_str, "%Y-%m-%d").date()
                days_since_visit = (today - last_visit).days
                if days_since_visit > 180:
                    variances.append(VarianceDetail(
                        description="Gap in chronic care follow-up",
                        expected_action="Routine follow-up within 6 months for chronic conditions",
                        actual_finding=f"No visit in the last {days_since_visit} days",
                        source=[SourceTrace(
                            type="visit_note",
                            description="Timeline analysis",
                            visit_number=len(visit_history)
                        )]
                    ))
            except (ValueError, TypeError):
                pass

    # --- 9. Missing Baseline Labs ---
    if cohort == "Poorly Controlled Diabetic" and len(visit_history) > 0:
        has_hba1c = any((v.get("labs") or {}).get("hba1c") is not None for v in visit_history)
        if not has_hba1c:
            variances.append(VarianceDetail(
                description="Missing baseline HbA1c for diabetic patient",
                expected_action="HbA1c lab order and results on file",
                actual_finding="No HbA1c results found in visit history",
                source=[SourceTrace(
                    type="lab",
                    description="Missing essential lab",
                    visit_number=len(visit_history)
                )]
            ))

    # --- 10. Medication Escalation ---
    if len(visit_history) >= 2:
        last_visit = visit_history[-1]
        prescriptions = last_visit.get("prescription", last_visit.get("medications_prescribed", []))
        if len(prescriptions) >= 3 and not advised_actions:
            # If multiple medications prescribed but NO advised actions/follow-ups pending
            variances.append(VarianceDetail(
                description="Medication escalated without clear follow-up plan",
                expected_action="Scheduled follow-up or lab check after prescribing 3+ medications",
                actual_finding=f"{len(prescriptions)} medications prescribed but 0 pending actions",
                source=[SourceTrace(
                    type="prescription",
                    description="Medication history vs advised actions",
                    visit_number=len(visit_history)
                )]
            ))

    detected = len(variances) > 0
    return CarePathVariance(
        detected=detected,
        variances=variances
    )

