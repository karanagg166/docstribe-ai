import json
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import List

from app.services.data_loader import load_patients, get_patient_by_id
from app.services.cache_service import get_cached_insights, save_insights, calculate_data_hash
from app.services.cohere_service import analyze_all_patients, stream_patient_analyses, aggregate_summary
from app.models.schemas import DashboardResponse, RiskLevel

logger = logging.getLogger(__name__)

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

@router.get("/dashboard/stream", summary="Stream patient analysis via SSE")
async def stream_dashboard():
    """SSE endpoint for progressive patient loading.

    - If cached data exists, all patients are sent as rapid-fire events (effectively instant).
    - If not cached, each patient is streamed the moment its LLM analysis completes.
    - After all patients arrive, the aggregated summary is sent.
    - The full response is saved to cache for future requests.
    """
    patients = load_patients()
    if not patients:
        async def error_stream():
            yield f"event: error\ndata: {json.dumps({'detail': 'No patient data available'})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    data_hash = calculate_data_hash(patients)

    # ── Cache hit: blast all events immediately ──
    cached_data = get_cached_insights(data_hash)
    if cached_data:
        async def cached_stream():
            try:
                response = DashboardResponse(**cached_data)
                total = len(response.patients)
                for i, patient in enumerate(response.patients):
                    event_data = {
                        "patient": patient.model_dump(mode="json"),
                        "index": i,
                        "total": total,
                    }
                    yield f"event: patient\ndata: {json.dumps(event_data, default=str)}\n\n"

                yield f"event: summary\ndata: {json.dumps(response.summary.model_dump(mode='json'), default=str)}\n\n"
                yield f"event: complete\ndata: {json.dumps({'from_cache': True, 'total_analyzed': total})}\n\n"
            except Exception as e:
                logger.error(f"Error streaming cached data: {e}", exc_info=True)
                yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"

        return StreamingResponse(cached_stream(), media_type="text/event-stream", headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        })

    # ── Cache miss: stream from LLM as each patient completes ──
    async def analysis_stream():
        all_insights = []
        total = len(patients)

        try:
            async for insight in stream_patient_analyses(patients):
                all_insights.append(insight)
                event_data = {
                    "patient": insight.model_dump(mode="json"),
                    "index": len(all_insights) - 1,
                    "total": total,
                }
                yield f"event: patient\ndata: {json.dumps(event_data, default=str)}\n\n"

            if all_insights:
                # Sort by risk and assign priority ranks
                risk_order = {RiskLevel.HIGH: 0, RiskLevel.MEDIUM: 1, RiskLevel.LOW: 2}
                all_insights.sort(key=lambda x: risk_order.get(x.risk_level, 1))
                for rank, ins in enumerate(all_insights):
                    ins.suggested_priority_rank = rank + 1

                summary = aggregate_summary(all_insights)

                # Save to cache
                full_response = DashboardResponse(
                    summary=summary,
                    patients=all_insights,
                    generated_at=datetime.utcnow(),
                    from_cache=False,
                )
                save_insights(data_hash, full_response.model_dump(mode="json"))

                yield f"event: summary\ndata: {json.dumps(summary.model_dump(mode='json'), default=str)}\n\n"

            yield f"event: complete\ndata: {json.dumps({'from_cache': False, 'total_analyzed': len(all_insights)})}\n\n"

        except Exception as e:
            logger.error(f"Error during streaming analysis: {e}", exc_info=True)
            yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"

    return StreamingResponse(analysis_stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })

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
