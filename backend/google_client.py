import json
import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from shared_state import redis_client, log_terminal

def get_gsc_service():
    """
    Loads credentials from Redis and builds an authorized GSC service object.
    Returns the service object or None if credentials are not found.
    """
    try:
        creds_json = redis_client.get("gsc_credentials")
        if not creds_json:
            log_terminal("⚠️  GSC credentials not found in Redis.")
            return None

        creds_data = json.loads(creds_json)
        credentials = Credentials(**creds_data)
        
        # Build the service object for the Search Console API
        service = build('searchconsole', 'v1', credentials=credentials)
        log_terminal("✅ Successfully built Google Search Console service object.")
        return service
        
    except Exception as e:
        log_terminal(f"❌ Failed to build GSC service: {e}")
        return None