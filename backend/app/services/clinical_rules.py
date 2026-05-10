"""Centralized clinical rules configuration.

Single source of truth for all vital thresholds, lab thresholds,
cohort classification rules, urgency keywords, and conversion barrier
keywords used across the deterministic engines.

To change a threshold, edit ONLY this file.
"""

from typing import Dict, List, Any


# ─── Vital Sign Thresholds ────────────────────────────────────────
# Used by: risk_engine, fallback_engine (_determine_risk, _extract_risk_flags)

VITAL_THRESHOLDS = {
    "bp_systolic_high": 160,       # ≥ this → HIGH risk
    "bp_systolic_elevated": 150,   # ≥ this → risk flag generated
    "hr_high": 100,                # ≥ this → HIGH risk
    "spo2_low": 94,                # < this → HIGH risk (hypoxemia)
    "temp_f_high": 100.4,          # > this → HIGH risk (fever)
}


# ─── Lab Thresholds ───────────────────────────────────────────────
# Used by: fallback_engine (_extract_risk_flags, _extract_progression_metrics)
#
# direction: "high_is_bad" → rising values are worsening
#            "low_is_bad"  → falling values are worsening
# delta: minimum change between first and last values to count as a trend

LAB_THRESHOLDS: Dict[str, Dict[str, Any]] = {
    "hba1c": {
        "elevated": 7.0,
        "critical": 8.0,
        "unit": "%",
        "direction": "high_is_bad",
        "delta": 0.2,
        "display_name": "HbA1c",
    },
    "creatinine": {
        "elevated": 1.2,
        "critical": 2.0,
        "unit": "mg/dL",
        "direction": "high_is_bad",
        "delta": 0.1,
        "display_name": "Creatinine",
    },
    "cholesterol": {
        "elevated": 200,
        "critical": 240,
        "unit": "mg/dL",
        "direction": "high_is_bad",
        "delta": 10,
        "display_name": "Cholesterol",
    },
    "tsh": {
        "elevated": 4.5,
        "critical": 10.0,
        "unit": "mIU/L",
        "direction": "high_is_bad",
        "delta": 1.0,
        "display_name": "TSH",
    },
    "egfr": {
        "elevated": 60,
        "critical": 30,
        "unit": "mL/min",
        "direction": "low_is_bad",
        "delta": 5,
        "display_name": "eGFR",
    },
    "ldl": {
        "elevated": 130,
        "critical": 160,
        "unit": "mg/dL",
        "direction": "high_is_bad",
        "delta": 10,
        "display_name": "LDL",
    },
    "hemoglobin": {
        "elevated": None,    # high hemoglobin is rarely flagged
        "critical": None,
        "low_threshold": 10.0,  # below this is concerning
        "unit": "g/dL",
        "direction": "low_is_bad",
        "delta": 0.5,
        "display_name": "Hemoglobin",
    },
}


# ─── Vital Sign Progression Tracking ─────────────────────────────
# Keys in visit["vitals"] that should be tracked longitudinally

TRACKABLE_VITALS = {
    "bp": {
        "extract": "systolic",    # extract systolic from "120/80" format
        "display_name": "Systolic BP",
        "unit": "mmHg",
        "direction": "high_is_bad",
        "delta": 5,
    },
    "hr": {
        "extract": "direct",
        "display_name": "Heart Rate",
        "unit": "bpm",
        "direction": "high_is_bad",
        "delta": 5,
    },
}


# ─── Comorbidity Threshold ────────────────────────────────────────

MULTI_MORBID_CONDITION_COUNT = 3   # ≥ this many known_conditions → HIGH risk


# ─── Cohort Classification Rules ─────────────────────────────────
# Weighted scoring system.
# search_fields determine points: primary presenting complaint is weighted highest.
FIELD_WEIGHTS = {
    "primary": 3,
    "department": 2,
    "conditions": 1
}

COHORT_RULES: List[Dict[str, Any]] = [
    {
        "keywords": ["cardiol", "angina", "cardiac", "cad"],
        "bucket": "Cardiac Intervention Pending",
    },
    {
        "keywords": ["diabet", "hba1c"],
        "bucket": "Poorly Controlled Diabetic",
    },
    {
        "keywords": ["hypertension", "htn"],
        "bucket": "Hypertension Follow-up",
    },
    {
        "keywords": ["ckd", "kidney", "renal"],
        "bucket": "CKD Follow-up",
    },
    {
        "keywords": ["neuro", "dystonia", "headache", "migrain", "parkinson", "stroke"],
        "bucket": "Neurological/Movement Disorder",
    },
    {
        "keywords": ["ortho", "arthro", "knee", "shoulder", "bone", "joint", "fracture"],
        "bucket": "Musculoskeletal/Surgical",
    },
    {
        "keywords": ["gastro", "gi", "liver", "hepat"],
        "bucket": "GI/Hepatobiliary",
    },
    {
        "keywords": ["infection", "fever"],
        "bucket": "Recurrent Infection",
    },
    {
        "keywords": ["post-op", "recovery", "post-procedure"],
        "bucket": "Post-Procedure Recovery",
    },
]

# Default cohort when nothing matches and condition count < MULTI_MORBID_CONDITION_COUNT
DEFAULT_COHORT = "General Follow-up"

# Cohort assigned when condition count >= MULTI_MORBID_CONDITION_COUNT
MULTI_MORBID_COHORT = "High-Risk Multi-Morbid"


# ─── Urgency Keywords ────────────────────────────────────────────
# If any of these appear in referral reason → HIGH risk

URGENCY_KEYWORDS = [
    "urgent", "severe", "emergency", "esrd", "dialysis",
    "status migrain", "critical", "life-threatening",
]


# ─── Conversion Barrier Keywords ──────────────────────────────────
# transcript keyword → human-readable label

BARRIER_KEYWORDS: Dict[str, str] = {
    "declined": "Patient declined treatment",
    "not interested": "Patient not interested",
    "refuses": "Patient refuses",
    "insurance": "Insurance barrier",
    "cost": "Financial barrier",
    "funds": "Financial barrier",
    "afford": "Financial barrier",
    "hometown": "Patient prefers hometown facility",
    "delay": "Patient deferring treatment",
    "wait": "Patient deferring treatment",
    "later": "Patient deferring treatment",
    "managing": "Patient self-managing",
    "physiotherapy": "Patient choosing conservative management",
}

# Conversion call outcome keywords
CONVERSION_DECLINED_KEYWORDS = ["declined", "not interested", "refuses", "declined admission"]
CONVERSION_FINANCIAL_KEYWORDS = ["insurance", "cost", "funds", "afford"]
CONVERSION_DEFERRING_KEYWORDS = ["delay", "wait", "later", "managing", "physiotherapy"]
CONVERSION_POSITIVE_KEYWORDS = ["interested", "agree", "ready", "proceed"]


# ─── Progression Keywords ────────────────────────────────────────
# Chief complaint keyword → progression status (fallback when no numeric trend)

WORSENING_KEYWORDS = ["worsening", "increasing", "persistent", "severe", "continuous"]
IMPROVING_KEYWORDS = ["improving", "better", "decreased", "resolved"]
RECURRING_KEYWORDS = ["recurrent", "recurring", "again"]


# ─── Helper: Match cohort from fields ─────────────────────────────

def match_cohort(department: str, conditions_joined: str, primary: str, condition_count: int) -> str:
    """Apply cohort rules using a weighted scoring system and return the matching bucket.

    Points are awarded based on where the keyword is found (e.g., primary=3, department=2, conditions=1).
    The bucket with the highest score wins.

    Args:
        department: lowercase department string
        conditions_joined: all known conditions joined and lowercased
        primary: lowercase primary condition/complaint
        condition_count: number of known conditions

    Returns:
        The cohort bucket string.
    """
    field_map = {
        "department": department,
        "conditions": conditions_joined,
        "primary": primary,
    }

    scores: Dict[str, int] = {rule["bucket"]: 0 for rule in COHORT_RULES}

    for rule in COHORT_RULES:
        for keyword in rule["keywords"]:
            for field_name, field_val in field_map.items():
                if field_val and keyword in field_val:
                    scores[rule["bucket"]] += FIELD_WEIGHTS.get(field_name, 1)

    max_score = 0
    best_bucket = DEFAULT_COHORT

    for bucket, score in scores.items():
        if score > max_score:
            max_score = score
            best_bucket = bucket

    # If the score is very low (e.g., just matched 1 or 2 condition keywords) 
    # but the patient is highly multi-morbid, classify them as multi-morbid
    if condition_count >= MULTI_MORBID_CONDITION_COUNT and max_score < 3:
        return MULTI_MORBID_COHORT

    if max_score == 0:
        if condition_count >= MULTI_MORBID_CONDITION_COUNT:
            return MULTI_MORBID_COHORT
        return DEFAULT_COHORT

    return best_bucket
