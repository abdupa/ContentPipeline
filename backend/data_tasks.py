import os
import json
import time
from dotenv import load_dotenv
from woocommerce import API
from shared_state import log_terminal

# --- Import the shared Celery app ---
from celery_app import app as celery_app

# --- CONFIGURATION & INITIALIZATION ---
load_dotenv()

PRODUCT_DB_PATH = "product_database.json"

def get_wc_api():
    wc_url = os.getenv("WC_URL")
    wc_key = os.getenv("WC_KEY")
    wc_secret = os.getenv("WC_SECRET")
    if not all([wc_url, wc_key, wc_secret]):
        log_terminal("❌ WooCommerce API credentials (WC_URL, WC_KEY, WC_SECRET) are not set in .env file.")
        return None
    return API(
        url=wc_url,
        consumer_key=wc_key,
        consumer_secret=wc_secret,
        version="wc/v3",
        timeout=30
    )

@celery_app.task
def update_product_database_task():
    try:
        log_terminal("--- [DATA TASK] Starting product database update... ---")
        wcapi = get_wc_api()
        if not wcapi:
            log_terminal("--- [DATA TASK] Aborting: WooCommerce API client not available. ---")
            return "Task failed: WooCommerce API not configured."
        all_products = []
        page = 1
        MAX_RETRIES = 3
        RETRY_DELAY = 5
        while True:
            products = None
            for attempt in range(MAX_RETRIES):
                try:
                    log_terminal(f"--- [DATA TASK] Fetching products page {page} (Attempt {attempt + 1}/{MAX_RETRIES})... ---")
                    products = wcapi.get("products", params={"per_page": 100, "page": page}).json()
                    break
                except Exception as e:
                    log_terminal(f"❌ [DATA TASK] Attempt {attempt + 1} failed for page {page}: {e}")
                    if attempt < MAX_RETRIES - 1:
                        log_terminal(f"--- [DATA TASK] Retrying in {RETRY_DELAY} seconds... ---")
                        time.sleep(RETRY_DELAY)
                    else:
                        log_terminal(f"❌ [DATA TASK] All retries failed for page {page}. Aborting task.")
                        raise
            if not products or not isinstance(products, list):
                log_terminal("--- [DATA TASK] No more products found or received invalid data. Ending fetch. ---")
                break
            for product in products:
                all_attributes = {
                    attr['name']: ", ".join(attr['options'])
                    for attr in product.get('attributes', []) if attr.get('options')
                }
                key_spec_names = [
                    "Chipset", "Display Type", "Display Size", "Display Resolution",
                    "Internal Memory", "Main Camera", "Selfie Camera", "Battery Type", "Battery Charging"
                ]
                key_specs = {
                    name: all_attributes.get(name)
                    for name in key_spec_names if all_attributes.get(name)
                }
                all_products.append({
                    "id": product.get('id'),
                    "name": product.get('name'),
                    "url": product.get('permalink'),
                    "price": product.get('price') or "N/A",
                    "sku": product.get('sku'),
                    "key_specs": key_specs
                })
            page += 1
            time.sleep(0.2)
        with open(PRODUCT_DB_PATH, 'w', encoding='utf-8') as f:
            json.dump(all_products, f, indent=2, ensure_ascii=False)
        success_message = f"✅ [DATA TASK] Successfully updated product database. Found {len(all_products)} products."
        log_terminal(success_message)
        return success_message
    except Exception as e:
        error_message = f"❌ [DATA TASK] A critical error occurred during product database update: {e}"
        log_terminal(error_message)
        return error_message
