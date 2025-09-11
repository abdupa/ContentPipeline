import os
import json
import time
import math 
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from woocommerce import API
from shared_state import log_terminal, redis_client
from sheet_parser import slugify
import sys

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

def _create_audit_log(status: str, total_found: int, total_synced: int, failed_ids: list, error_message: str = None):
    """A helper function to create and save a detailed audit log."""
    log_entry = {
        "task_name": "deep_sync_product_database",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_products_on_wc": total_found,
        "products_synced_successfully": total_synced,
        "products_failed_to_sync": len(failed_ids),
        "failed_product_ids": failed_ids,
        "error_message": error_message
    }
    
    # Print a summary to the main log
    log_terminal("--- [DEEP SYNC AUDIT LOG] ---")
    log_terminal(f"    - Status: {status}")
    log_terminal(f"    - Total Products on WooCommerce: {total_found}")
    log_terminal(f"    - Synced Successfully: {total_synced}")
    log_terminal(f"    - Failed: {len(failed_ids)}")
    if error_message:
        log_terminal(f"    - Final Error: {error_message}")
    log_terminal("-----------------------------")

    # Append the detailed log entry to a persistent file
    try:
        with open("audit_log.jsonl", 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception as e:
        log_terminal(f"    - ⚠️ CRITICAL: Failed to write to audit_log.jsonl: {e}")


@celery_app.task
def update_product_database_task():
    """
    (DEEP SYNC v2 - WITH RETRIES & AUDIT)
    Builds a 100% accurate mirror of the live WooCommerce database by fetching
    each product individually. Includes per-product retries and a final audit log.
    """
    all_product_ids = []
    failed_ids = []
    
    try:
        log_terminal("--- [DEEP SYNC] Starting full product database synchronization... ---")
        wcapi = get_wc_api()
        if not wcapi:
            raise Exception("WooCommerce API client not available.")

        # --- STEP 1: EFFICIENTLY FETCH ALL PRODUCT IDs ---
        page = 1
        log_terminal("    - Step 1: Fetching all product IDs...")
        while True:
            try:
                products_batch = wcapi.get("products", params={"per_page": 100, "page": page, "status": "publish", "_fields": "id"}).json()
                if not products_batch: break
                all_product_ids.extend([p['id'] for p in products_batch])
                log_terminal(f"    - Found {len(all_product_ids)} IDs so far...")
                page += 1
            except Exception as e:
                log_terminal(f"    - ❌ ERROR fetching product ID list on page {page}: {e}")
                break
        
        log_terminal(f"    - Found a total of {len(all_product_ids)} products to sync.")
        
        # --- STEP 2: LOOP AND DEEP SYNC EACH PRODUCT ---
        all_products = []
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # --- Tunable Constants for Retry Logic ---
        POLITE_DELAY_SECONDS = 0.5 
        MAX_SINGLE_PRODUCT_RETRIES = 3
        RETRY_DELAY_SECONDS = 5

        for index, product_id in enumerate(all_product_ids):
            log_terminal(f"    - Syncing product {index + 1}/{len(all_product_ids)} (ID: {product_id})...")
            
            # --- NEW: Per-Product Retry Loop ---
            synced_successfully = False
            for attempt in range(MAX_SINGLE_PRODUCT_RETRIES):
                try:
                    fields = "id,name,slug,permalink,price,regular_price,sale_price,external_url,button_text,attributes,meta_data"
                    product = wcapi.get(f"products/{product_id}", params={"_fields": fields}).json()
                    
                    meta_map = {item['key']: item['value'] for item in product.get('meta_data', [])}
                    key_specs = {
                        attr['name']: ", ".join(attr['options'])
                        for attr in product.get('attributes', []) if attr.get('options')
                    }
                    price_to_seed = product.get('sale_price') or product.get('regular_price') or None
                    
                    all_products.append({
                        "id": product.get('id'), "name": product.get('name'), "url": product.get('permalink'),
                        "price": product.get('price') or "N/A", "sku": product.get('sku'), "key_specs": key_specs,
                        "slug": product.get('slug'), "permalink": product.get('permalink'), "sale_price": product.get('sale_price'),
                        "regular_price": product.get('regular_price'), "external_url": product.get('external_url'),
                        "button_text": product.get('button_text'), "shopee_id": meta_map.get('_shopee_id'),
                        "lazada_id": meta_map.get('_lazada_id'), "shop_id": meta_map.get('_shop_id'),
                        "price_history": json.loads(meta_map.get('_price_history', '[]')),
                    })
                    
                    synced_successfully = True
                    break # Success! Exit the retry loop.

                except requests.exceptions.RequestException as e:
                    log_terminal(f"    - ⚠️ WARNING: (Attempt {attempt + 1}/{MAX_SINGLE_PRODUCT_RETRIES}) Network/API error for ID {product_id}. Status: {e.response.status_code if e.response else 'N/A'}.")
                    if attempt < MAX_SINGLE_PRODUCT_RETRIES - 1:
                        time.sleep(RETRY_DELAY_SECONDS)
                except Exception as e:
                    log_terminal(f"    - ⚠️ WARNING: (Attempt {attempt + 1}) An unexpected error occurred for product ID {product_id}: {e}. This error will not be retried.")
                    break # Don't retry unknown errors

            if not synced_successfully:
                log_terminal(f"    - ❌ CRITICAL: Failed to sync product ID {product_id} after {MAX_SINGLE_PRODUCT_RETRIES} attempts. Skipping.")
                failed_ids.append(product_id)

            time.sleep(POLITE_DELAY_SECONDS)

        # --- 3. Save the complete file ONCE ---
        with open(PRODUCT_DB_PATH, 'w', encoding='utf-8') as f:
            json.dump(all_products, f, indent=2, ensure_ascii=False)
        
        # --- 4. NEW: Create Final Audit Log ---
        _create_audit_log(status="SUCCESS", total_found=len(all_product_ids), total_synced=len(all_products), failed_ids=failed_ids)
        return f"Deep Sync complete. Synced {len(all_products)}/{len(all_product_ids)} products."
        
    except Exception as e:
        error_message = f"A critical, unhandled error occurred: {e}"
        log_terminal(f"❌ [DEEP SYNC] {error_message}")
        # --- 4. NEW: Create Final Audit Log (on failure) ---
        _create_audit_log(status="FAILED", total_found=len(all_product_ids), total_synced=0, failed_ids=all_product_ids, error_message=error_message)
        raise e

@celery_app.task(bind=True)
def update_woocommerce_products_task(self, job_id: str, approved_products: list):
    """
    (FINAL, DEBUGGED VERSION)
    Correctly finds products using a type-safe router and syncs them.
    Includes detailed logging for the matching process.
    """
    job_key = f"job:{job_id}"
    audit_key = f"audit_log:{job_id}"
    log_terminal(f"--- [ROBUST SYNC - P3] Starting job {job_id} for {len(approved_products)} products. ---")
    
    CHUNK_SIZE, MAX_API_RETRIES, RETRY_DELAY_SECONDS, POLITE_DELAY_SECONDS = 25, 3, 5, 1

    def update_job_status(status, message):
        redis_client.set(job_key, json.dumps({"job_id": job_id, "status": status, "message": message}), ex=3600)

    update_job_status("processing", f"Starting sync for {len(approved_products)} products...")
    
    wcapi = get_wc_api()
    if not wcapi:
        update_job_status("failed", "WooCommerce API not configured.")
        return "Task failed: WooCommerce API not configured."

    try:
        with open(PRODUCT_DB_PATH, 'r', encoding='utf-8') as f:
            local_products = json.load(f)
        product_map_by_id = {prod['id']: prod for prod in local_products if 'id' in prod}
        
        wc_full_batch_payload = []
        audit_log_entries = []
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        log_terminal(f"    - DEBUG: Built product_map_by_id with {len(product_map_by_id)} integer keys.")

        for approved_prod in approved_products:
            action = approved_prod.get('action')
            target_db_id = None
            
            raw_id_to_find = None
            if action == 'approve':
                raw_id_to_find = approved_prod.get('matched_db_id')
                log_terminal(f"    - DEBUG: Action is 'approve'. Raw ID from payload: {raw_id_to_find} (type: {type(raw_id_to_find)})")
            elif action == 'link':
                raw_id_to_find = approved_prod.get('linked_db_id')
                log_terminal(f"    - DEBUG: Action is 'link'. Raw ID from payload: {raw_id_to_find} (type: {type(raw_id_to_find)})")
            
            if raw_id_to_find is not None:
                try:
                    target_db_id = int(raw_id_to_find)
                except (ValueError, TypeError):
                    log_terminal(f"    - ⚠️ WARNING: Could not convert ID '{raw_id_to_find}' to integer. Skipping.")
            
            local_prod_to_update = product_map_by_id.get(target_db_id) if target_db_id else None
            log_terminal(f"    - DEBUG: Lookup result for integer ID {target_db_id}: {'FOUND' if local_prod_to_update else 'NOT FOUND'}")

            if local_prod_to_update:
                wc_id = local_prod_to_update.get('id')
                new_name, new_sale_price, new_regular_price, new_aff_link, new_btn_text = (
                    approved_prod.get('parsed_name'), approved_prod.get('new_sale_price'),
                    approved_prod.get('new_regular_price'), approved_prod.get('affiliate_link'),
                    approved_prod.get('button_text') or "Check Price"
                )
                local_prod_to_update.update({
                    'name': new_name, 'shopee_id': approved_prod.get('shopee_id'),
                    'lazada_id': approved_prod.get('lazada_id'), 'shop_id': approved_prod.get('shop_id'),
                    'external_url': new_aff_link, 'button_text': new_btn_text
                })
                meta_data_list = [
                    {"key": "_shopee_id", "value": str(approved_prod.get('shopee_id') or "")},
                    {"key": "_lazada_id", "value": str(approved_prod.get('lazada_id') or "")},
                    {"key": "_shop_id", "value": str(approved_prod.get('shop_id') or "")}
                ]
                product_api_data = {"id": wc_id, "type": "external", "name": new_name, "external_url": new_aff_link, "button_text": new_btn_text, "meta_data": []}
                final_sale_price_str, final_reg_price_str, final_main_price_str, price_to_log = "", "", "", None
                if new_sale_price and new_regular_price:
                    final_sale_price_str, final_reg_price_str, final_main_price_str, price_to_log = str(new_sale_price), str(new_regular_price), str(new_sale_price), new_sale_price
                elif new_regular_price:
                    final_reg_price_str, final_main_price_str, price_to_log = str(new_regular_price), str(new_regular_price), new_regular_price
                elif new_sale_price:
                    final_reg_price_str, final_main_price_str, price_to_log = str(new_sale_price), str(new_sale_price), new_sale_price
                product_api_data.update({'price': final_main_price_str, 'regular_price': final_reg_price_str, 'sale_price': final_sale_price_str})
                current_price_str = local_prod_to_update.get('sale_price') or local_prod_to_update.get('regular_price')
                history_json_string = json.dumps(local_prod_to_update.get('price_history', []))
                current_price_float = None
                try:
                    current_price_float = float(current_price_str)
                except (ValueError, TypeError): pass
                price_changed = price_to_log is not None and price_to_log != current_price_float
                if price_changed:
                    local_prod_to_update.update({'sale_price': new_sale_price, 'regular_price': new_regular_price})
                    history = local_prod_to_update.get('price_history', [])
                    if not history and current_price_float is not None:
                        history.append({"date": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"), "price": current_price_float})
                    history.append({"date": today_str, "price": price_to_log})
                    local_prod_to_update['price_history'] = history
                    history_json_string = json.dumps(history)
                meta_data_list.append({"key": "_price_history", "value": history_json_string})
                product_api_data['meta_data'] = meta_data_list
                audit_entry = {
                    "name": new_name,
                    "wc_id": wc_id,
                    "status": "Price Updated" if price_changed else "Synced",
                    "price_before": current_price_float,
                    "price_after": price_to_log if price_changed else current_price_float,
                    "details": "Meta-data (Shopee/Lazada ID, History, etc.) was refreshed."
                }
                audit_log_entries.append(audit_entry)
                wc_full_batch_payload.append(product_api_data)
        
        if not wc_full_batch_payload:
            update_job_status("complete", "Sync complete. No products required an update.")
            return "Sync complete. No products required an update."

        chunks = [wc_full_batch_payload[i:i + CHUNK_SIZE] for i in range(0, len(wc_full_batch_payload), CHUNK_SIZE)]
        total_chunks, failed_chunks_count = len(chunks), 0
        log_terminal(f"    - Starting batch sync of {len(wc_full_batch_payload)} products in {total_chunks} chunk(s) of {CHUNK_SIZE}...")
        for i, chunk in enumerate(chunks):
            chunk_num = i + 1
            log_terminal(f"    - Processing chunk {chunk_num}/{total_chunks}...")
            update_job_status("processing", f"Syncing chunk {chunk_num}/{total_chunks}...")
            sent_successfully = False
            for attempt in range(MAX_API_RETRIES):
                try:
                    response = wcapi.post("products/batch", {"update": chunk})
                    response_json = response.json()
                    if response.status_code >= 400:
                        log_terminal(f"    - ❌ API ERROR: Chunk {chunk_num} (Attempt {attempt + 1}) failed: {json.dumps(response_json)}")
                        raise requests.exceptions.HTTPError(f"Batch update failed: {response_json.get('message', 'Unknown API Error')}", response=response)
                    log_terminal(f"    - DEBUG: WC Success Response: {json.dumps(response_json)}")
                    sent_successfully = True
                    log_terminal(f"    - ✅ Chunk {chunk_num}/{total_chunks} synced successfully.")
                    break
                except requests.exceptions.RequestException as e:
                    log_terminal(f"    - ⚠️ NETWORK ERROR: Chunk {chunk_num} (Attempt {attempt + 1}): {e}")
                    if attempt < MAX_API_RETRIES - 1: time.sleep(RETRY_DELAY_SECONDS)
                    else: failed_chunks_count += 1
                except Exception as e:
                    log_terminal(f"    - ❌ UNEXPECTED ERROR on Chunk {chunk_num} (Attempt {attempt + 1}): {e}")
                    if attempt < MAX_API_RETRIES - 1: time.sleep(RETRY_DELAY_SECONDS)
                    else: failed_chunks_count += 1
            if sent_successfully and total_chunks > 1: time.sleep(POLITE_DELAY_SECONDS)

        with open(PRODUCT_DB_PATH, 'w', encoding='utf-8') as f:
            json.dump(local_products, f, indent=2, ensure_ascii=False)
        log_terminal("    - ✅ Local product_database.json saved.")
        
        redis_client.set(audit_key, json.dumps(audit_log_entries), ex=86400)
        log_terminal(f"    - ✅ Audit log for job {job_id} saved to Redis.")

        if failed_chunks_count > 0:
            final_message = f"Sync complete with errors. {failed_chunks_count} of {total_chunks} chunks failed."
            update_job_status("failed", final_message)
            raise Exception(final_message)
        else:
            final_message = f"Successfully synced all {len(wc_full_batch_payload)} products."
            update_job_status("complete", final_message)
            return final_message
    except Exception as e:
        error_message = f"A critical, unhandled error occurred: {e}"
        update_job_status("failed", str(e))
        raise e

# @celery_app.task(bind=True)
# def update_woocommerce_products_task(self, job_id: str, approved_products: list):
#     """
#     (ROBUST VERSION)
#     Receives approved products, splits them into chunks, and syncs each chunk
#     to WooCommerce with retries, delays, and error handling. Updates the local DB once.
#     """
#     job_key = f"job:{job_id}"
#     log_terminal(f"--- [ROBUST SYNC - P3] Starting job {job_id} for {len(approved_products)} products. ---")
    
#     # --- Tunable Constants ---
#     CHUNK_SIZE = 25            # Number of products per API batch call (WC limit is 100)
#     MAX_API_RETRIES = 3        # How many times to retry a single failed chunk
#     RETRY_DELAY_SECONDS = 5    # How long to wait between failed attempts
#     POLITE_DELAY_SECONDS = 1   # How long to wait between SUCCESSFUL chunks

#     # --- Job Status Helper ---
#     def update_job_status(status, message):
#         redis_client.set(job_key, json.dumps({
#             "job_id": job_id, "status": status, "message": message
#         }), ex=3600)

#     update_job_status("processing", f"Starting sync for {len(approved_products)} products...")
    
#     wcapi = get_wc_api()
#     if not wcapi:
#         update_job_status("failed", "WooCommerce API not configured.")
#         return

#     try:
#         # 1. Load local DB (This logic is the same as before)
#         with open(PRODUCT_DB_PATH, 'r', encoding='utf-8') as f:
#             local_products = json.load(f)
#         # product_map_by_slug = {prod['slug']: prod for prod in local_products if 'slug' in prod}
#         product_map_by_id = {prod['id']: prod for prod in local_products if 'id' in prod}
        
#         wc_full_batch_payload = []  # We still build the FULL list of payloads first
#         today_str = datetime.now().strftime("%Y-%m-%d")
#         updated_local_count = 0

#         # 2. Build the Payloads (This logic is the same as before)
#         for approved_prod in approved_products:
            
#             action = approved_prod.get('action')
#             target_db_id = None # This will store the final, clean integer ID

#             # --- NEW, TYPE-SAFE ROUTING LOGIC ---
#             raw_id_to_find = None
#             if action == 'approve':
#                 # This was a pre-matched item. Get its ID from the Phase 1 data.
#                 raw_id_to_find = approved_prod.get('matched_db_id')
            
#             elif action == 'link':
#                 # This is a manually linked item. Get its ID from the Phase 2 UI data.
#                 raw_id_to_find = approved_prod.get('linked_db_id')
            
#             # Safely convert the found ID (which could be a str or int) to a clean integer
#             if raw_id_to_find is not None:
#                 try:
#                     target_db_id = int(raw_id_to_find)
#                 except (ValueError, TypeError):
#                     log_terminal(f"    - ⚠️ WARNING: Could not convert ID '{raw_id_to_find}' to integer for product '{approved_prod.get('parsed_name')}'. Skipping.")
#             # --- END OF FIX ---

#             # If we have a valid target ID, find the product in our ID map
#             local_prod_to_update = product_map_by_id.get(target_db_id) if target_db_id else None

#             # If we successfully found the product in our DB, proceed with the update
#             if local_prod_to_update:
#                 wc_id = local_prod_to_update.get('id') 

#                 # --- 1. GET DATA FROM THE APPROVED PAYLOAD ---
#                 source = approved_prod.get('source') # 'shopee' or 'lazada'
#                 if not source:
#                     continue # Skip if the source is unknown

#                 # --- 2. UPDATE SOURCE-SPECIFIC DATA IN LOCAL DB OBJECT ---
                
#                 # Ensure the main 'linked_sources' dictionary exists
#                 if 'linked_sources' not in local_prod_to_update:
#                     local_prod_to_update['linked_sources'] = {}
                
#                 # Get the existing data for this specific source (e.g., Shopee's data)
#                 source_data = local_prod_to_update['linked_sources'].get(source, {})

#                 # "Preserve Link" Logic: Use existing link if it's there, otherwise use the new one.
#                 existing_aff_link = source_data.get('affiliate_url')
#                 generated_aff_link = approved_prod.get('affiliate_link')
#                 final_affiliate_link = existing_aff_link if existing_aff_link else generated_aff_link

#                 # Update the source-specific data
#                 source_data['product_id'] = approved_prod.get(f'{source}_id')
#                 source_data['shop_id'] = approved_prod.get('shop_id')
#                 source_data['sale_price'] = approved_prod.get('new_sale_price')
#                 source_data['regular_price'] = approved_prod.get('new_regular_price')
#                 source_data['affiliate_url'] = final_affiliate_link
#                 source_data['last_updated'] = datetime.now(timezone.utc).isoformat()
                
#                 # Append to the source-specific price history
#                 current_source_price = source_data.get('sale_price') or source_data.get('regular_price')
#                 history = source_data.get('price_history', [])
#                 if not history or (history and history[-1].get('price') != current_source_price):
#                     history.append({"date": today_str, "price": current_source_price})
#                 source_data['price_history'] = history
                
#                 # Save the fully updated source data back to the main DB object
#                 local_prod_to_update['linked_sources'][source] = source_data

#                 # --- 3. DETERMINE WINNING PRICE (Lowest Price Logic) ---
#                 winning_source_key = None
#                 lowest_price = float('inf')
                
#                 for source_key, data in local_prod_to_update.get('linked_sources', {}).items():
#                     price = data.get('sale_price') or data.get('regular_price')
#                     if price is not None and price < lowest_price:
#                         lowest_price = price
#                         winning_source_key = source_key
                
#                 # --- 4. UPDATE TOP-LEVEL DB FIELDS WITH WINNER'S DATA ---
#                 if winning_source_key:
#                     winning_source_data = local_prod_to_update['linked_sources'][winning_source_key]
                    
#                     # Apply price logic for the winner
#                     win_sale = winning_source_data.get('sale_price')
#                     win_reg = winning_source_data.get('regular_price')

#                     # Update top-level fields in our local DB object
#                     local_prod_to_update['current_sale_price'] = win_sale
#                     local_prod_to_update['current_regular_price'] = win_reg
#                     local_prod_to_update['current_source'] = winning_source_key
#                     local_prod_to_update['current_affiliate_url'] = winning_source_data.get('affiliate_url')
#                     local_prod_to_update['button_text'] = f"Buy on {winning_source_key.capitalize()}"

#                     # --- 5. BUILD FINAL WC API PAYLOAD (using winner's data) ---
#                     final_sale_price_str = str(win_sale) if win_sale else ""
#                     final_reg_price_str = str(win_reg) if win_reg else ""
#                     final_main_price_str = final_sale_price_str or final_reg_price_str

#                     meta_data_list = [
#                         {"key": "_shopee_id", "value": str(local_prod_to_update['linked_sources'].get('shopee', {}).get('product_id') or "")},
#                         {"key": "_lazada_id", "value": str(local_prod_to_update['linked_sources'].get('lazada', {}).get('product_id') or "")},
#                         {"key": "_price_history", "value": json.dumps(winning_source_data.get('price_history', []))}
#                     ]
                    
#                     product_api_data = {
#                         "id": wc_id,
#                         "type": "external",
#                         "name": local_prod_to_update.get('name'),
#                         "price": final_main_price_str,
#                         "regular_price": final_reg_price_str,
#                         "sale_price": final_sale_price_str,
#                         "external_url": winning_source_data.get('affiliate_url'),
#                         "button_text": f"Buy on {winning_source_key.capitalize()}",
#                         "meta_data": meta_data_list
#                     }
                    
#                     wc_full_batch_payload.append(product_api_data)
#                     updated_local_count += 1
                
#         # --- 3. NEW: CHUNKING, RETRY, AND DELAY LOGIC ---
#         if not wc_full_batch_payload:
#             log_terminal("    - No matched products found to update. Task complete.")
#             update_job_status("complete", "Sync complete. No matched products required an update.")
#             return "Sync complete. No matched products required an update."

#         # Split our full payload list into a list of smaller chunks
#         chunks = [wc_full_batch_payload[i:i + CHUNK_SIZE] for i in range(0, len(wc_full_batch_payload), CHUNK_SIZE)]
#         total_chunks = len(chunks)
#         failed_chunks_count = 0
        
#         log_terminal(f"    - Starting batch sync of {len(wc_full_batch_payload)} products in {total_chunks} chunk(s) of {CHUNK_SIZE}...")

#         for i, chunk in enumerate(chunks):
#             chunk_num = i + 1
#             log_terminal(f"    - Processing chunk {chunk_num}/{total_chunks}...")
#             update_job_status("processing", f"Syncing chunk {chunk_num}/{total_chunks}...")
            
#             sent_successfully = False
#             for attempt in range(MAX_API_RETRIES):
#                 try:
#                     batch_data = {"update": chunk}
#                     response = wcapi.post("products/batch", batch_data)
#                     response_json = response.json() # Get the JSON response regardless of status

#                     if response.status_code >= 400:
#                         # This is a WooCommerce API error (e.g., bad data, invalid SKU, etc.)
#                         log_terminal(f"    - ❌ API ERROR: Chunk {chunk_num} (Attempt {attempt + 1}) failed with Status {response.status_code}.")
#                         log_terminal(f"    - WC Response: {json.dumps(response_json)}") # LOG THE FULL ERROR
#                         # We raise an exception to trigger the retry
#                         raise requests.exceptions.HTTPError(f"Batch update failed: {response_json.get('message', 'Unknown API Error')}", response=response)
                    
#                     # If we get here, the status code was 2xx (Success)
#                     sent_successfully = True
#                     log_terminal(f"    - ✅ Chunk {chunk_num}/{total_chunks} synced successfully.")
#                     break  # Success! Exit the retry loop.

#                 except requests.exceptions.RequestException as e:
#                     # This catches network errors, timeouts, 503s, etc.
#                     log_terminal(f"    - ⚠️ NETWORK ERROR: Chunk {chunk_num} (Attempt {attempt + 1}/{MAX_API_RETRIES}) failed: {e}")
#                     if attempt < MAX_API_RETRIES - 1:
#                         time.sleep(RETRY_DELAY_SECONDS) # Wait before retrying
#                     else:
#                         log_terminal(f"    - ❌ CRITICAL: Chunk {chunk_num} FAILED permanently after {MAX_API_RETRIES} attempts.")
#                         failed_chunks_count += 1
                
#                 except Exception as e:
#                     # Catches other unexpected errors (like the response not being JSON)
#                     log_terminal(f"    - ❌ UNEXPECTED ERROR on Chunk {chunk_num} (Attempt {attempt + 1}): {e}")
#                     if attempt < MAX_API_RETRIES - 1:
#                         time.sleep(RETRY_DELAY_SECONDS)
#                     else:
#                         log_terminal(f"    - ❌ CRITICAL: Chunk {chunk_num} FAILED permanently. Error type: {type(e)}")
#                         failed_chunks_count += 1

#             if sent_successfully and total_chunks > 1:
#                 time.sleep(POLITE_DELAY_SECONDS) # Be nice to the API between successful calls

#         # --- 4. Final Local DB Save (Only ONCE) ---
#         log_terminal(f"    - All chunks processed. Saving {updated_local_count} updates to local product_database.json...")
#         with open(PRODUCT_DB_PATH, 'w', encoding='utf-8') as f:
#             json.dump(local_products, f, indent=2, ensure_ascii=False)
#         log_terminal("    - ✅ Local product_database.json saved.")

#         # --- 5. Final Report ---
#         if failed_chunks_count > 0:
#             final_message = f"Sync complete with errors. {failed_chunks_count} out of {total_chunks} chunks failed."
#             log_terminal(f"❌ [PHASE 3 SYNC] {final_message}")
#             update_job_status("failed", final_message) # Mark job as failed if any chunk failed
#             raise Exception(final_message)
#         else:
#             final_message = f"Successfully synced all {len(wc_full_batch_payload)} products in {total_chunks} chunks."
#             log_terminal(f"✅ [PHASE 3 SYNC] Job {job_id} complete. {final_message}")
#             update_job_status("complete", final_message)
#             return final_message

#     except Exception as e:
#         error_message = f"❌ [PHASE 3 SYNC] A critical, unhandled error occurred: {e}"
#         log_terminal(error_message)
#         update_job_status("failed", str(e))
#         raise e  # Re-raise to make Celery mark the task as FAILED

@celery_app.task(bind=True)
def inspect_wc_product_task(self, job_id: str, product_id: int):
    """
    Fetches the raw JSON for a single WC product and saves it to a
    job key in Redis for the user to view.
    """
    log_terminal(f"--- [INSPECTOR TASK] Running live lookup for Product ID: {product_id} ---")
    wcapi = get_wc_api()
    if not wcapi:
        redis_client.set(job_id, json.dumps({"status": "failed", "error": "WooCommerce API not configured."}), ex=600)
        return

    try:
        # Make the API call to fetch the single product
        response = wcapi.get(f"products/{product_id}")
        response.raise_for_status()
        product_data = response.json()
        
        # Save the complete JSON response to the job_id key for the frontend to fetch
        redis_client.set(job_id, json.dumps({"status": "complete", "data": product_data}), ex=600)
        log_terminal(f"    - ✅ Inspector success. Saved data to job {job_id}")

    except requests.exceptions.RequestException as e:
        error_message = f"Failed to fetch product. Status: {e.response.status_code}. Response: {e.response.json()}"
        log_terminal(f"    - ❌ Inspector failed: {error_message}")
        redis_client.set(job_id, json.dumps({"status": "failed", "error": error_message}), ex=600)
    except Exception as e:
        log_terminal(f"    - ❌ Inspector failed with unexpected error: {e}")
        redis_client.set(job_id, json.dumps({"status": "failed", "error": str(e)}), ex=600)

def run_inspector(product_id: str):
    """
    Synchronous (immediate) function to fetch and print product data.
    """
    log_terminal(f"--- [COMMAND TOOL] Running live lookup for Product ID: {product_id} ---")
    wcapi = get_wc_api()
    if not wcapi:
        log_terminal("--- [COMMAND TOOL] FAILED: Cannot get WC API credentials.")
        return

    try:
        # Get the live product data from WooCommerce
        response = wcapi.get(f"products/{product_id}")
        response.raise_for_status() # Raise error for 4xx/5xx status
        product_data = response.json()
        
        # Pretty-print the full JSON response directly to the terminal
        print("\n--- [COMMAND TOOL] SUCCESS: Full Live Product Data ---")
        print(json.dumps(product_data, indent=2))
        print("------------------------------------------------------\n")
        
    except requests.exceptions.RequestException as e:
        # Handle API errors gracefully
        try:
            error_data = e.response.json()
            log_terminal(f"--- [COMMAND TOOL] FAILED: {e.response.status_code} Error ---")
            print(json.dumps(error_data, indent=2)) # Print the WC error (e.g., "Product not found")
        except:
            log_terminal(f"--- [COMMAND TOOL] FAILED with a network or non-JSON error: {e} ---")
    except Exception as e:
         log_terminal(f"--- [COMMAND TOOL] FAILED with an unexpected error: {e} ---")

# This special "if" block makes our file runnable as a script
# from the command line.
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python data_tasks.py <product_id_to_check>")
        sys.exit(1)
    
    product_id_arg = sys.argv[1]
    run_inspector(product_id_arg)