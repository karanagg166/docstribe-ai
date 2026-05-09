from pydantic_settings import BaseSettings
from pydantic import ConfigDict
import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent

# On Vercel (serverless), the filesystem is read-only except /tmp
IS_VERCEL = os.environ.get("VERCEL") == "1"
if IS_VERCEL:
    DATA_DIR = Path("/tmp/docstribe_data")
    CACHE_DIR = Path("/tmp/docstribe_cache")
else:
    DATA_DIR = BASE_DIR / "data"
    CACHE_DIR = DATA_DIR / ".cache"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
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
    
    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

settings = Settings()
