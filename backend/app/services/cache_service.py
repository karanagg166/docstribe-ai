import json
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime
from app.config import settings, CACHE_DIR

def _json_serializer(obj):
    """Custom JSON serializer for objects not serializable by default json."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def _get_cache_file_path() -> str:
    """Returns the path to the cache file."""
    return CACHE_DIR / "insights_cache.json"

def calculate_data_hash(data: Any) -> str:
    """Calculate an MD5 hash of the data structure to detect changes."""
    data_str = json.dumps(data, sort_keys=True, default=_json_serializer)
    return hashlib.md5(data_str.encode()).hexdigest()

def get_cached_insights(data_hash: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached insights if the data hash matches.
    If the data has changed, the hash won't match, meaning we need to re-run the LLM.
    """
    cache_path = _get_cache_file_path()
    if not cache_path.exists():
        return None
        
    try:
        with open(cache_path, "r") as f:
            cache_data = json.load(f)
            
        # Check if hash matches
        if cache_data.get("data_hash") == data_hash:
            return cache_data.get("insights")
        return None
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to read cache: {e}")
        return None

def save_insights(data_hash: str, insights: Dict[str, Any]) -> bool:
    """Save insights and the data hash to the cache file."""
    cache_path = _get_cache_file_path()
    cache_data = {
        "data_hash": data_hash,
        "timestamp": datetime.utcnow().isoformat(),
        "insights": insights
    }
    
    try:
        with open(cache_path, "w") as f:
            json.dump(cache_data, f, indent=2, default=_json_serializer)
        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to write cache: {e}")
        return False
