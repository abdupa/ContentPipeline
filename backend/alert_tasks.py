# alert_tasks.py

import json
from shared_state import redis_client, log_terminal
from celery_app import app as celery_app

@celery_app.task
def create_price_alert_task(subscription_data: dict):
    """
    Saves a user's price alert subscription to a dedicated list in Redis.
    """
    try:
        product_id = subscription_data.get('product_id')
        if not product_id:
            log_terminal("❌ PRICE ALERT FAILED: No product_id provided.")
            return

        # We will store all subscriptions for a single product in one list.
        redis_key = f"price_alerts:{product_id}"
        
        # Save the subscription data as a JSON string
        redis_client.lpush(redis_key, json.dumps(subscription_data))
        
        log_terminal(f"✅ New price alert subscribed for product ID {product_id} from {subscription_data.get('email')}.")

    except Exception as e:
        log_terminal(f"❌ CRITICAL ERROR in create_price_alert_task: {e}")
        # Re-raise the exception so Celery can track the failure
        raise e