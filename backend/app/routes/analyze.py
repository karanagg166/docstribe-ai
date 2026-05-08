from fastapi import APIRouter, HTTPException
from typing import List

from app.services.data_loader import load_patients, get_patient_by_id
from app.services.cache_service import get_cached_insights, save_insights, calculate_data_hash
from app.services.cohere_service import analyze_all_patients
from app.models.schemas import DashboardResponse

router = APIRouter()

@router.get("/patients", summary="Get all raw patients")
async def get_raw_patients():
    """Returns the raw patient data directly from the JSON file."""
    patients = load_patients()
    if not patients:
        return {"patients": [], "message": "No patient data found. Please add data to patients.json."}
    return {"patients": patients, "count": len(patients)}

@router.get("/patients/{patient_id}", summary="Get raw patient by ID")
async def get_raw_patient(patient_id: str):
    """Returns raw data for a specific patient."""
    patient = get_patient_by_id(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
    return patient

@router.get("/dashboard", response_model=DashboardResponse, summary="Get analyzed dashboard data")
async def get_dashboard():
    """
    Main endpoint for the frontend dashboard.
    Will return cached insights or trigger LLM analysis if cache is invalid/stale.
    """
    patients = load_patients()
    if not patients:
        raise HTTPException(status_code=404, detail="No patient data available for analysis.")
        
    data_hash = calculate_data_hash(patients)
    
    # 1. Try Cache
    cached_data = get_cached_insights(data_hash)
    if cached_data:
        return DashboardResponse(**cached_data)
        
    # 2. If no cache or hash mismatch, analyze with LLM
    response = await analyze_all_patients(patients)
    
    # 3. Save to cache
    save_insights(data_hash, response.model_dump(mode="json"))
    
    return response

@router.post("/analyze/force", response_model=DashboardResponse, summary="Force re-analysis of all patients")
async def force_analyze_all():
    """Force re-analysis of all patients, bypassing cache."""
    patients = load_patients()
    if not patients:
        raise HTTPException(status_code=404, detail="No patient data available for analysis.")
        
    response = await analyze_all_patients(patients)
    
    data_hash = calculate_data_hash(patients)
    save_insights(data_hash, response.model_dump(mode="json"))
    
    return response
