from pydantic_settings import BaseSettings
from pydantic import ConfigDict
import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent

# The data directory is always relative to the codebase for reading static files
DATA_DIR = BASE_DIR / "data"

# On Vercel (serverless), the filesystem is read-only except /tmp
IS_VERCEL = os.environ.get("VERCEL") == "1"
if IS_VERCEL:
    CACHE_DIR = Path("/tmp/docstribe_cache")
else:
    CACHE_DIR = DATA_DIR / ".cache"

# Ensure directories exist
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    pass # Read-only filesystem on Vercel, directory should already exist
CACHE_DIR.mkdir(parents=True, exist_ok=True)

class Settings(BaseSettings):
    app_env: str = "development"
    allowed_origins: str = "http://localhost:3000"
    
    # LLM
    cohere_api_key: str = ""
    
    # Database (optional, user might use file cache)
    database_url: str = ""
    
    # Cache settings
    cache_ttl_hours: int = 6
    
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
    # Strip whitespace/newlines from string variables
    def __init__(self, **data):
        super().__init__(**data)
        if isinstance(self.app_env, str):
            self.app_env = self.app_env.strip()
        if isinstance(self.allowed_origins, str):
            self.allowed_origins = self.allowed_origins.strip()
        if isinstance(self.cohere_api_key, str):
            self.cohere_api_key = self.cohere_api_key.strip()
        if isinstance(self.database_url, str):
            self.database_url = self.database_url.strip()
    
    @property
    def cors_origins(self) -> list[str]:
        origins = [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]
        # Always allow Vercel frontend domains for SSE streaming
        vercel_origins = [
            "https://docstribe-frontend.vercel.app",
            "https://docstribe-ai.vercel.app",
            "https://docstribe-frontend-karan-aggarwals-projects.vercel.app",
            "https://docstribe-backend-karan-aggarwals-projects.vercel.app",
        ]
        for vo in vercel_origins:
            if vo not in origins:
                origins.append(vo)
        return origins

settings = Settings()
