import json
import hashlib
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from app.config import settings, CACHE_DIR

logger = logging.getLogger(__name__)

# Cache TTL in seconds (default 2 hours)
CACHE_TTL_SECONDS = 7200

def _json_serializer(obj):
    """Custom JSON serializer for objects not serializable by default json."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    # Pydantic models might sometimes leak through
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    raise TypeError(f"Type {type(obj)} not serializable")

def _get_cache_file_path() -> str:
    """Returns the path to the cache file."""
    # Ensure cache directory exists
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / "insights_cache.json"

# Update this version whenever clinical logic or prompts change to invalidate the cache
LOGIC_VERSION = "v1.1-deterministic-logic"

def calculate_data_hash(data: Any) -> str:
    """Calculate an MD5 hash of the data structure + logic version to detect changes."""
    try:
        # Combine data with logic version to ensure code changes trigger a refresh
        combined_data = {
            "version": LOGIC_VERSION,
            "data": data
        }
        data_str = json.dumps(combined_data, sort_keys=True, default=_json_serializer)
        return hashlib.md5(data_str.encode()).hexdigest()
    except Exception as e:
        logger.error(f"Failed to calculate hash: {e}")
        # Fallback to random hash to force cache miss on failure
        import uuid
        return uuid.uuid4().hex

def get_cached_insights(data_hash: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached insights if the data hash matches AND TTL has not expired.
    If the data has changed, the hash won't match, meaning we need to re-run the LLM.
    """
    try:
        cache_path = _get_cache_file_path()
        if not cache_path.exists():
            return None
            
        with open(cache_path, "r") as f:
            cache_data = json.load(f)
            
        # Check if hash matches
        if cache_data.get("data_hash") != data_hash:
            return None
            
        # Check TTL
        cached_time_str = cache_data.get("timestamp")
        if not cached_time_str:
            return None
            
        cached_time = datetime.fromisoformat(cached_time_str)
        if datetime.utcnow() - cached_time > timedelta(seconds=CACHE_TTL_SECONDS):
            logger.info("Cache expired due to TTL")
            return None
            
        logger.info("Cache hit!")
        return cache_data.get("insights")
        
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning(f"Cache file corrupted or invalid: {e}")
        return None
    except Exception as e:
        logger.warning(f"Failed to read cache: {e}")
        return None

def save_insights(data_hash: str, insights: Dict[str, Any]) -> bool:
    """Save insights and the data hash to the cache file."""
    try:
        cache_path = _get_cache_file_path()
        cache_data = {
            "data_hash": data_hash,
            "timestamp": datetime.utcnow().isoformat(),
            "insights": insights
        }
        
        # Write to a temporary file first, then rename (atomic write)
        temp_path = cache_path.with_suffix('.tmp')
        with open(temp_path, "w") as f:
            json.dump(cache_data, f, indent=2, default=_json_serializer)
            
        temp_path.replace(cache_path)
        logger.info("Cache updated successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to write cache: {e}")
        # Try to clean up temp file if it exists
        try:
            temp_path = _get_cache_file_path().with_suffix('.tmp')
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass
        return False
