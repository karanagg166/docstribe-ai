from app.models.schemas import CarePathVariance, VarianceDetail, SourceTrace
from typing import List
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

def detect_variances(patient: dict) -> CarePathVariance:
    """
    Rule-based variance detection as validation layer.
    
    Detects:
    1. Overdue advised actions (due_date in the past, status still "pending")
    2. Multiple pending actions (2+ pending)
    3. Call log: patient declined
    4. Call log: financial/insurance barrier
    5. Call log: patient deferring/avoiding
    6. Call log: patient unreachable (2+ no_answer)
    """
    variances: List[VarianceDetail] = []
    today = date.today()
    
    # --- 1 & 2: Check advised_actions ---
    advised_actions = patient.get("advised_actions", [])
    pending_actions = [a for a in advised_actions if str(a.get("status", "")).lower() == "pending"]
    overdue_actions = []
    
    for action in pending_actions:
        due_date_str = action.get("due_date", "")
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
                description=f"Overdue: {action.get('title', 'Action')} was due {action.get('due_date', 'unknown')}",
                expected_action=f"Complete {action.get('action_type', 'action')}: {action.get('title', '')}",
                actual_finding=f"Status is still 'pending' past due date ({action.get('due_date', '')})",
                source=[SourceTrace(
                    type="visit_note",
                    description=f"Advised action: {action.get('title', '')}",
                    visit_number=len(patient.get("visit_history", []))
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
                visit_number=len(patient.get("visit_history", []))
            )]
        ))
    
    # --- 3-6: Check call_history ---
    call_history = patient.get("call_history", [])
    
    decline_keywords = ["declined", "not interested", "refuses", "refused", "not proceeding", "firm"]
    financial_keywords = ["cost", "insurance", "funds", "afford", "money", "payment", "tpa", "lacks funds"]
    deferral_keywords = ["delay", "wait", "later", "managing", "physiotherapy", "hometown", "consider", "wants to discuss"]
    
    no_answer_count = 0
    
    for call in call_history:
        outcome = str(call.get("outcome", "")).lower()
        summary = str(call.get("transcript_summary", "")).lower()
        call_date = call.get("call_date", "")
        
        # Track no-answers
        if outcome in ["no_answer", "no answer", "not_connected", "switched_off"]:
            no_answer_count += 1
            continue
        
        # Decline detection
        if any(kw in summary for kw in decline_keywords):
            variances.append(VarianceDetail(
                description="Patient declined treatment/admission",
                expected_action="Patient acceptance of advised procedure/admission",
                actual_finding=f"Call on {call_date}: Patient expressed refusal or disinterest",
                source=[SourceTrace(
                    type="visit_note",
                    description=f"Call log: {call.get('transcript_summary', '')[:100]}",
                    visit_number=len(patient.get("visit_history", []))
                )]
            ))
        
        # Financial barrier detection
        if any(kw in summary for kw in financial_keywords):
            variances.append(VarianceDetail(
                description="Financial/insurance barrier identified",
                expected_action="Clear financial pathway for admission (insurance approval, payment plan)",
                actual_finding=f"Call on {call_date}: Financial or insurance concern raised",
                source=[SourceTrace(
                    type="visit_note",
                    description=f"Call log: {call.get('transcript_summary', '')[:100]}",
                    visit_number=len(patient.get("visit_history", []))
                )]
            ))
        
        # Deferral detection
        if any(kw in summary for kw in deferral_keywords):
            variances.append(VarianceDetail(
                description="Patient deferring/avoiding treatment",
                expected_action="Timely scheduling of advised procedure",
                actual_finding=f"Call on {call_date}: Patient indicated deferral or avoidance",
                source=[SourceTrace(
                    type="visit_note",
                    description=f"Call log: {call.get('transcript_summary', '')[:100]}",
                    visit_number=len(patient.get("visit_history", []))
                )]
            ))
    
    # Unreachable patient (2+ no_answer)
    if no_answer_count >= 2:
        variances.append(VarianceDetail(
            description=f"Patient unreachable ({no_answer_count} failed contact attempts)",
            expected_action="Successful patient contact for follow-up coordination",
            actual_finding=f"{no_answer_count} call attempts resulted in no answer",
            source=[SourceTrace(
                type="visit_note",
                description="Multiple failed contact attempts",
                visit_number=len(patient.get("visit_history", []))
            )]
        ))

    # --- Legacy checks for backward compatibility ---
    visits = patient.get("visits", [])
    if len(visits) >= 3:
        med_count = sum(1 for v in visits if len(v.get("medications_prescribed", [])) > 2)
        if med_count >= 3:
            variances.append(VarianceDetail(
                description="Medication escalated 3+ times without stabilization",
                expected_action="Stabilization of condition with current meds",
                actual_finding="Multiple medication changes across recent visits",
                source=[SourceTrace(type="prescription", description="Medication history", visit_number=len(visits))]
            ))

    detected = len(variances) > 0
    return CarePathVariance(
        detected=detected,
        variances=variances
    )
