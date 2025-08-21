import redis
import json
import logging
from datetime import datetime, timezone

# Connect to our Redis container
redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

# A shared helper function for console logging
def log_terminal(message):
    print(message)
    logging.info(message)

# --- NEW: Action History Logger ---
def log_action(action: str, details: dict = None):
    """
    Logs a user action to a Redis list for an audit trail.
    """
    try:
        log_entry = {
            "action": action,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        # LPUSH adds the new log to the beginning of the list.
        # LTRIM keeps the list capped at 1000 entries to prevent infinite growth.
        redis_client.lpush("action_history", json.dumps(log_entry))
        redis_client.ltrim("action_history", 0, 999)
        log_terminal(f"ACTION_LOG: {action}")
    except Exception as e:
        log_terminal(f"❌ Could not log action '{action}': {e}")