from typing import Dict, Any, List

def calculate_deterministic_risk(patient: Dict[str, Any]) -> str:
    """
    Fallback/Validation deterministic risk calculation.
    
    Checks (in order of severity):
    1. Urgency keywords
    2. Vital sign thresholds
    3. Multi-morbidity with any abnormal vital
    4. Elective procedure
    """
    
    # 1. Urgency Check
    opd_details = patient.get("opd_details", {})
    urgency = opd_details.get("admission_advised", {}).get("urgency", "").lower()
    referral = patient.get("current_referral", {})
    urgency_reason = (referral.get("op_advised_reason", "") or "").lower()
    
    if urgency in ["emergency", "urgent"]:
        return "High"
    
    # Check urgency reason for critical keywords
    critical_keywords = ["esrd", "dialysis", "status migrainosus", "emergency", "urgent", "critical"]
    if any(kw in urgency_reason for kw in critical_keywords):
        return "High"
        
    # 2. Vitals Check — handle both string and int formats from patients.json
    visit_history = patient.get("visit_history", [])
    latest_vitals = {}
    if visit_history:
        latest_vitals = visit_history[-1].get("vitals", {})
    
    # Also check legacy format
    clinical = patient.get("clinical_data", {})
    legacy_vitals = clinical.get("latest_visit", {}).get("vitals", {})
    vitals = latest_vitals or legacy_vitals
    
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
        
        if hr > 110 or hr < 50 or bp_sys > 180 or bp_sys < 90 or spo2 < 94 or temp > 100.4:
            return "High"
    except Exception:
        pass  # If we can't parse, continue to next check
    
    # 3. Multi-morbidity check
    history = patient.get("history", {})
    known_conditions = history.get("known_conditions", [])
    presenting = history.get("presenting_complaints", [])
    condition_count = len(known_conditions) + len(presenting)
    
    # If 3+ conditions and any abnormal vital, it's High
    if condition_count >= 3:
        try:
            if (hr_raw and (hr > 100 or hr < 55)) or \
               (bp_raw and (bp_sys > 160 or bp_sys < 95)) or \
               (spo2_raw and spo2 < 95):
                return "High"
        except Exception:
            pass
        # Even without abnormal vitals, 3+ conditions is at least Medium
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
