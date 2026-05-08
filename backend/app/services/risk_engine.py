from typing import Dict, Any

def calculate_deterministic_risk(patient: Dict[str, Any]) -> str:
    """
    Fallback/Validation deterministic risk calculation.
    
    1. Check Urgency
    2. Check Vitals
    """
    
    # 1. Urgency Check
    opd_details = patient.get("opd_details", {})
    urgency = opd_details.get("admission_advised", {}).get("urgency", "").lower()
    
    if urgency in ["emergency", "urgent"]:
        return "High"
        
    # 2. Vitals Check
    clinical = patient.get("clinical_data", {})
    vitals = clinical.get("latest_visit", {}).get("vitals", {})
    
    # Very basic vitals checks
    try:
        hr = int(vitals.get("heart_rate", "0").replace(" bpm", ""))
        bp_sys = int(vitals.get("blood_pressure", "120/80").split("/")[0])
        
        if hr > 110 or hr < 50 or bp_sys > 180 or bp_sys < 90:
            return "High"
    except Exception:
        pass # If we can't parse, ignore
        
    if urgency == "elective":
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
