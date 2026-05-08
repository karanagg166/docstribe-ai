from app.models.schemas import CarePathVariance, VarianceDetail, SourceTrace
from typing import List

def detect_variances(patient: dict) -> CarePathVariance:
    """
    Rule-based variance detection as validation layer.
    """
    variances: List[VarianceDetail] = []
    
    # Extract historical context
    visits = patient.get("visits", [])
    
    # 1. Check: labs ordered but no results in subsequent visits
    labs_ordered = set()
    for v in visits:
        for lab in v.get("labs_ordered", []):
            labs_ordered.add(lab.lower())
    
    # This is a naive check; in a real scenario we'd look at results, 
    # but the patient JSON schema here relies on visit notes and vitals
    # We will simulate the check:
    # If more than 2 visits and lab ordered in first visit without results in later visits
    
    # Let's do a basic variance check based on "advised" or "pending" status
    status = patient.get("status", "").lower()
    if "pending" in status or "overdue" in status:
        variances.append(VarianceDetail(
            description="Pending action is overdue",
            expected_action="Completion of advised procedure/lab",
            actual_finding=f"Status is currently {status}",
            source=[SourceTrace(type="visit_note", description="Patient status check", visit_number=len(visits))]
        ))

    # Just a placeholder for more complex rule-based logic
    if len(visits) >= 3:
        # Check medication escalation
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
