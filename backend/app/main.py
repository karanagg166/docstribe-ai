import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routes import analyze

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Docstribe AI - OPD Clinical Dashboard",
    description="LLM-powered OPD Clinical Dashboard API",
    version="1.0.0",
)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred.", "error": str(exc)},
    )

@app.get("/", tags=["System"])
async def root():
    """Root endpoint."""
    return {"service": "Docstribe AI Backend", "status": "running", "version": "1.0.0"}

@app.get("/api/health", tags=["System"])
async def health_check():
    """Basic health check endpoint."""
    cohere_status = "configured" if settings.cohere_api_key else "missing"
    return {
        "status": "ok", 
        "environment": settings.app_env,
        "cohere_api_key": cohere_status
    }

# Include routers
app.include_router(analyze.router, prefix="/api", tags=["Analysis"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
