import json
import logging
from pathlib import Path
from app.config import DATA_DIR

logger = logging.getLogger(__name__)

PATIENTS_FILE = DATA_DIR / "patients.json"

def load_patients() -> list[dict]:
    """Loads patients from the JSON file."""
    if not PATIENTS_FILE.exists():
        logger.warning(f"Patients file not found at {PATIENTS_FILE}. Returning empty list.")
        return []
        
    try:
        with open(PATIENTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Ensure it's a list even if the user pasted a single object or wrapped object
            if isinstance(data, dict):
                # If wrapped like {"patients": [...]}, extract it
                for key in ["patients", "data"]:
                    if key in data and isinstance(data[key], list):
                        return data[key]
                return [data]
            elif isinstance(data, list):
                return data
            else:
                logger.error("Invalid JSON format in patients.json. Expected list or dict.")
                return []
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing patients.json: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error loading patients.json: {e}")
        return []

def get_patient_by_id(patient_id: str) -> dict | None:
    """Gets a specific patient by ID from the JSON file."""
    patients = load_patients()
    for patient in patients:
        # Check common ID fields
        if str(patient.get("id", "")) == patient_id or str(patient.get("patient_id", "")) == patient_id:
            return patient
    return None
