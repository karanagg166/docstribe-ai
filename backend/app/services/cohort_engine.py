from app.services.clinical_rules import match_cohort, DEFAULT_COHORT


def get_cohort_bucket(patient: dict) -> str:
    """
    Rule-based cohort classification fallback.
    Delegates to clinical_rules.match_cohort for config-driven matching.
    """
    department = patient.get("department", "").lower()
    condition = patient.get("primary_condition", "").lower()

    # Collect known conditions for multi-morbid counting
    known = patient.get("known_conditions", [])
    if isinstance(known, list):
        cond_s = " ".join(c.lower() for c in known) + " " + condition
        num_conditions = len(known)
    else:
        cond_s = condition
        num_conditions = 1

    return match_cohort(department, cond_s, condition, num_conditions)
