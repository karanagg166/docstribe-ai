from typing import Dict, Any, List
from app.services.clinical_rules import (
    VITAL_THRESHOLDS,
    URGENCY_KEYWORDS,
    MULTI_MORBID_CONDITION_COUNT,
    LAB_THRESHOLDS
)

def calculate_deterministic_risk(patient: Dict[str, Any]) -> str:
    """
    Fallback/Validation deterministic risk calculation.
    
    Checks (in order of severity):
    1. Urgency keywords
    2. Vital sign thresholds
    3. Critical lab thresholds
    4. Multi-morbidity with any abnormal vital/lab
    5. Elective procedure
    """
    
    # 1. Urgency Check
    opd_details = patient.get("opd_details", {})
    urgency = opd_details.get("admission_advised", {}).get("urgency", "").lower()
    referral = patient.get("current_referral", {})
    urgency_reason = (referral.get("op_advised_reason", "") or "").lower()
    
    if urgency in ["emergency", "urgent"]:
        return "High"
    
    # Check urgency reason for critical keywords
    if any(kw in urgency_reason for kw in URGENCY_KEYWORDS):
        return "High"
        
    # 2. Vitals Check — handle both string and int formats from patients.json
    visit_history = patient.get("visit_history", [])
    latest_visit = visit_history[-1] if visit_history else {}
    latest_vitals = latest_visit.get("vitals", {})
    latest_labs = latest_visit.get("labs", {})
    
    # Also check legacy format
    clinical = patient.get("clinical_data", {})
    legacy_visit = clinical.get("latest_visit", {})
    legacy_vitals = legacy_visit.get("vitals", {})
    vitals = latest_vitals or legacy_vitals
    
    hr_raw = None
    hr = 0
    bp_raw = None
    bp_sys = 120
    spo2_raw = None
    spo2 = 99
    temp_raw = None
    temp = 98.6
    
    try:
        # Heart rate — may be int or string like "88 bpm"
        hr_raw = vitals.get("hr") or vitals.get("heart_rate", 0)
        hr = int(str(hr_raw).replace(" bpm", "").strip()) if hr_raw else 0
        
        # Blood pressure — may be "162/96" format or separate fields
        bp_raw = vitals.get("bp") or vitals.get("blood_pressure", "120/80")
        bp_sys = int(str(bp_raw).split("/")[0].strip()) if bp_raw else 120
        
        # SpO2
        spo2_raw = vitals.get("spo2", 99)
        spo2 = int(str(spo2_raw).replace("%", "").strip()) if spo2_raw else 99
        
        # Temperature
        temp_raw = vitals.get("temp_f") or vitals.get("temperature", 98.6)
        temp = float(str(temp_raw).replace("°F", "").strip()) if temp_raw else 98.6
        
        if (hr > VITAL_THRESHOLDS["hr_high"] or hr < 50 or 
            bp_sys > VITAL_THRESHOLDS["bp_systolic_high"] or bp_sys < 90 or 
            spo2 < VITAL_THRESHOLDS["spo2_low"] or 
            temp > VITAL_THRESHOLDS["temp_f_high"]):
            return "High"
    except Exception:
        pass  # If we can't parse, continue to next check
        
    # 3. Labs Check - Check if any lab crosses critical threshold
    labs = latest_labs or legacy_visit.get("labs", {})
    try:
        for lab_key, val in labs.items():
            if val is None:
                continue
            lab_cfg = LAB_THRESHOLDS.get(lab_key)
            if not lab_cfg:
                continue
                
            critical_thresh = lab_cfg.get("critical")
            if critical_thresh is None:
                continue
                
            direction = lab_cfg.get("direction", "high_is_bad")
            val_float = float(val)
            
            if direction == "high_is_bad" and val_float >= critical_thresh:
                return "High"
            elif direction == "low_is_bad" and val_float <= critical_thresh:
                return "High"
    except Exception:
        pass

    # 4. Multi-morbidity check
    history = patient.get("history", {})
    known_conditions = history.get("known_conditions", [])
    presenting = history.get("presenting_complaints", [])
    condition_count = len(known_conditions) + len(presenting)
    
    # If >= MULTI_MORBID_CONDITION_COUNT conditions and any abnormal vital/lab, it's High
    if condition_count >= MULTI_MORBID_CONDITION_COUNT:
        try:
            # For multi-morbidity, we use slightly lower thresholds (elevated rather than high)
            if (hr_raw and (hr > 100 or hr < 55)) or \
               (bp_raw and (bp_sys > VITAL_THRESHOLDS["bp_systolic_elevated"] or bp_sys < 95)) or \
               (spo2_raw and spo2 < 95):
                return "High"
                
            # Also check elevated labs for multi-morbid patients
            for lab_key, val in labs.items():
                if val is None:
                    continue
                lab_cfg = LAB_THRESHOLDS.get(lab_key)
                if not lab_cfg:
                    continue
                    
                elevated_thresh = lab_cfg.get("elevated")
                if elevated_thresh is None:
                    continue
                    
                direction = lab_cfg.get("direction", "high_is_bad")
                val_float = float(val)
                
                if direction == "high_is_bad" and val_float >= elevated_thresh:
                    return "High"
                elif direction == "low_is_bad" and val_float <= elevated_thresh:
                    return "High"
        except Exception:
            pass
        # Even without abnormal vitals/labs, MULTI_MORBID_CONDITION_COUNT+ conditions is at least Medium
        return "Medium"
        
    if urgency == "elective":
        return "Medium"
    
    # Check if any procedure is advised — that's at least Medium
    referral = patient.get("current_referral", {})
    if referral.get("op_advised", False):
        return "Medium"
        
    return "Low"

def validate_llm_risk(llm_risk: str, deterministic_risk: str) -> str:
    """
    Ensure the LLM doesn't downgrade a definitively High risk patient.
    """
    if deterministic_risk == "High" and llm_risk != "High":
        # Override the LLM
        return "High"
    return llm_risk

