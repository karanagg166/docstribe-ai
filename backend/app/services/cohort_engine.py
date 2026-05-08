from app.models.schemas import CohortBucket

def get_cohort_bucket(patient: dict) -> CohortBucket:
    """
    Rule-based cohort classification fallback.
    Maps department + conditions + procedures → cohort bucket
    """
    department = patient.get("department", "").lower()
    condition = patient.get("primary_condition", "").lower()
    
    # Check for High-Risk Multi-Morbid (multiple chronic conditions)
    # Simple heuristic: if there's a comma or "and" in primary condition, 
    # or age > 75 with multiple visits. (Just a basic rule for fallback)
    if " and " in condition or "," in condition:
        return CohortBucket.HIGH_RISK_MULTIMORBID
        
    if "cardio" in department or "heart" in condition or "cad" in condition:
        # Check if intervention pending
        if "pending" in str(patient).lower() and ("angio" in str(patient).lower() or "cabg" in str(patient).lower()):
            return CohortBucket.CARDIAC_INTERVENTION_PENDING
        return CohortBucket.HTN_FOLLOWUP

    if "neuro" in department or "parkinson" in condition or "stroke" in condition:
        return CohortBucket.NEUROLOGICAL_DISORDER

    if "nephro" in department or "ckd" in condition or "kidney" in condition:
        return CohortBucket.CKD_FOLLOWUP

    if "ortho" in department or "bone" in condition or "joint" in condition or "fracture" in condition:
        return CohortBucket.MUSCULOSKELETAL_SURGICAL

    if "gastro" in department or "liver" in condition or "gi" in condition or "hepat" in condition:
        return CohortBucket.GI_HEPATOBILIARY

    if "diabet" in condition:
        return CohortBucket.POORLY_CONTROLLED_DIABETIC

    if "infection" in condition or "fever" in condition:
        return CohortBucket.RECURRENT_INFECTION

    if "post-op" in condition or "recovery" in condition:
        return CohortBucket.POST_PROCEDURE

    # Default fallback
    return CohortBucket.GENERAL_FOLLOWUP
