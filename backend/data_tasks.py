import os
import json
import time
import math 
import re
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from woocommerce import API
from shared_state import log_terminal, redis_client
from sheet_parser import slugify
import sys
from google_sheets import get_sheets_service, fetch_sheet_grid
from sheet_parser import (
    clean_product_name, extract_prices_shopee, extract_hyperlink_from_cell,
    slugify, convert_to_affiliate_link, parse_ecommerce_url,
    extract_prices_lazada, clean_product_name_lazada
)
from thefuzz import process as fuzz_process, fuzz
from itertools import islice

# --- Import the shared Celery app ---
from celery_app import app as celery_app

# --- CONFIGURATION & INITIALIZATION ---
load_dotenv()

PRODUCT_DB_PATH = "product_database.json"

def prices_match(price_a, price_b):
    if price_a in (None, "") and price_b in (None, ""):
        return True
    try:
        return math.isclose(float(price_a), float(price_b), rel_tol=0, abs_tol=0.01)
    except (TypeError, ValueError):
        return str(price_a or "") == str(price_b or "")

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
    (DEEP SYNC v3.1 - REFINED LOGGING)
    Builds an accurate mirror of the live WooCommerce database with the new
    multi-source schema, now with clearer, more detailed logging for progress and errors.
    """
    all_product_ids = []
    failed_ids = []
    
    try:
        log_terminal("--- [DEEP SYNC] Starting full product database synchronization... ---")
        wcapi = get_wc_api()
        if not wcapi:
            raise Exception("WooCommerce API client not available.")

        # --- STEP 1: EFFICIENTLY FETCH ALL PRODUCT IDs (Unchanged) ---
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
        POLITE_DELAY_SECONDS = 1 
        MAX_SINGLE_PRODUCT_RETRIES = 3
        RETRY_DELAY_SECONDS = 5

        for index, product_id in enumerate(all_product_ids):
            # REFINED: Clearer per-product heading
            log_terminal(f"--- Syncing product {index + 1}/{len(all_product_ids)} (ID: {product_id}) ---")

            synced_successfully = False
            for attempt in range(MAX_SINGLE_PRODUCT_RETRIES):
                try:
                    fields = "id,name,slug,permalink,price,regular_price,sale_price,sku,external_url,button_text,attributes,meta_data"
                    product = wcapi.get(f"products/{product_id}", params={"_fields": fields}).json()
                    
                    # (The data processing logic is unchanged from your working version)
                    meta_map = {item['key']: item['value'] for item in product.get('meta_data', [])}
                    key_specs = {attr['name']: ", ".join(attr['options']) for attr in product.get('attributes', []) if attr.get('options')}
                    linked_sources = {}
                    sources_to_check = ['shopee', 'lazada'] # Can be expanded in the future

                    for source in sources_to_check:
                        # Check if this source has any price data to indicate it's active
                        if meta_map.get(f'_{source}_price'):
                            linked_sources[source] = {
                                "product_id": meta_map.get(f'_{source}_id'),
                                "sale_price": float(meta_map.get(f'_{source}_price')) if meta_map.get(f'_{source}_price') else None,
                                "regular_price": None, # Note: We don't store a separate regular price per source in WC meta
                                "affiliate_url": meta_map.get(f'_{source}_url'),
                                "last_updated": meta_map.get(f'_{source}_last_updated'),
                                "price_history": json.loads(meta_map.get(f'_{source}_price_history', '[]')),
                            }
                    product_data = {
                        "id": product.get('id'), "name": product.get('name'), "sku": product.get('sku'), "slug": product.get('slug'), "permalink": product.get('permalink'), "key_specs": key_specs,
                        "price": product.get('price') or "N/A", "sale_price": product.get('sale_price'), "regular_price": product.get('regular_price'), "external_url": product.get('external_url'), "button_text": product.get('button_text'), "shopee_id": meta_map.get('_shopee_id'),
                        "lazada_id": meta_map.get('_lazada_id'), "shop_id": meta_map.get('_shop_id'), "price_history": json.loads(meta_map.get('_price_history', '[]')),
                        "current_sale_price": product.get('sale_price') or product.get('regular_price'), "current_source": "woocommerce", "linked_sources": linked_sources,
                    }
                    
                    all_products.append(product_data)
                    synced_successfully = True
                    break # Success! Exit the retry loop.

                except requests.exceptions.RequestException as e:
                    # REFINED: More detailed network error logging
                    log_terminal(f"    - ⚠️ WARNING (Attempt {attempt + 1}/{MAX_SINGLE_PRODUCT_RETRIES}): Network error. Status: {e.response.status_code if e.response else 'N/A'}. Retrying in {RETRY_DELAY_SECONDS}s...")
                    time.sleep(RETRY_DELAY_SECONDS)
                except Exception as e:
                    log_terminal(f"    - ❌ An unexpected error occurred: {e}. This product will not be retried.")
                    break

            # NEW: Final status log for each product
            if synced_successfully:
                log_terminal(f"    - ✅ SUCCESS: Product ID {product_id} synced.")
            else:
                log_terminal(f"    - ❌ FAILED: Product ID {product_id} could not be synced after {MAX_SINGLE_PRODUCT_RETRIES} attempts.")
                failed_ids.append(product_id)

            time.sleep(POLITE_DELAY_SECONDS)

        # --- 3. Save & Audit (Unchanged) ---
        with open(PRODUCT_DB_PATH, 'w', encoding='utf-8') as f:
            json.dump(all_products, f, indent=2, ensure_ascii=False)
        
        _create_audit_log(status="SUCCESS", total_found=len(all_product_ids), total_synced=len(all_products), failed_ids=failed_ids)
        return f"Deep Sync complete. Synced {len(all_products)}/{len(all_product_ids)} products."
        
    except Exception as e:
        error_message = f"A critical, unhandled error occurred: {e}"
        log_terminal(f"❌ [DEEP SYNC] {error_message}")
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

    def prices_match(price_a, price_b):
        if price_a in (None, "") and price_b in (None, ""):
            return True
        try:
            return math.isclose(float(price_a), float(price_b), rel_tol=0, abs_tol=0.01)
        except (TypeError, ValueError):
            return str(price_a or "") == str(price_b or "")

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

@celery_app.task(bind=True)
def update_multi_source_products_task(self, job_id: str, approved_products: list):
    """
    (MULTI-SOURCE ENGINE v1.1 - WITH DETAILED DEBUG LOGGING)
    Processes approved products, updates multi-source data in the local DB,
    determines the 'winning' price, and syncs all source data to WooCommerce.
    """
    job_key = f"job:{job_id}"
    audit_key = f"audit_log:{job_id}"
    log_terminal(f"--- [MULTI-SOURCE SYNC] Starting job {job_id} for {len(approved_products)} products. ---")

    CHUNK_SIZE, MAX_API_RETRIES, RETRY_DELAY_SECONDS, POLITE_DELAY_SECONDS = 25, 3, 5, 1

    def update_job_status(status, message):
        redis_client.set(job_key, json.dumps({"job_id": job_id, "status": status, "message": message}), ex=3600)

    update_job_status("processing", f"Starting multi-source sync for {len(approved_products)} products...")
    
    wcapi = get_wc_api()
    if not wcapi:
        update_job_status("failed", "WooCommerce API not configured.")
        return "Task failed: WooCommerce API not configured."

    try:
        with open(PRODUCT_DB_PATH, 'r', encoding='utf-8') as f:
            local_products = json.load(f)
        product_map_by_id = {prod['id']: prod for prod in local_products if 'id' in prod}
        
        # NEW LOG: Confirm that our lookup map was built correctly
        log_terminal(f"    - DEBUG: Built local product map with {len(product_map_by_id)} entries.")
        
        wc_full_batch_payload = []
        audit_log_entries = []
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        for index, approved_prod in enumerate(approved_products):
            log_terminal(f"--- Processing Approved Product {index + 1}/{len(approved_products)} ---") # NEW LOG
            log_terminal(f"    - Raw Payload: {approved_prod}") # NEW LOG

            action = approved_prod.get('action')
            target_db_id = None
            raw_id_to_find = approved_prod.get('matched_db_id') if action == 'approve' else approved_prod.get('linked_db_id')
            
            log_terminal(f"    - Action is '{action}'. Raw ID from payload: {raw_id_to_find} (type: {type(raw_id_to_find)})") # NEW LOG

            if raw_id_to_find is not None:
                try: 
                    target_db_id = int(raw_id_to_find)
                    log_terminal(f"    - Successfully converted raw ID to integer: {target_db_id}") # NEW LOG
                except (ValueError, TypeError): 
                    log_terminal(f"    - ⚠️ WARNING: Could not convert ID '{raw_id_to_find}' to integer. Skipping product.")
                    continue # Skip this product if ID is invalid
            
            local_prod_to_update = product_map_by_id.get(target_db_id) if target_db_id else None
            
            # CRITICAL NEW LOG: This tells us if the match was successful
            log_terminal(f"    - Lookup result for integer ID {target_db_id}: {'FOUND' if local_prod_to_update else 'NOT FOUND'}")

            if local_prod_to_update:
                previous_price = local_prod_to_update.get('current_sale_price') or local_prod_to_update.get('current_regular_price') or local_prod_to_update.get('sale_price')
                source = approved_prod.get('source')
                if not source: 
                    log_terminal("    - ⚠️ WARNING: 'source' field not found in payload. Skipping.") # NEW LOG
                    continue

                log_terminal(f"    - Step A: Updating source '{source}' data in local DB object...") # NEW LOG
                if 'linked_sources' not in local_prod_to_update: local_prod_to_update['linked_sources'] = {}
                source_data = local_prod_to_update['linked_sources'].get(source, {})
                source_data = local_prod_to_update['linked_sources'].get(source, {})

                # 1. Safely get the existing history BEFORE we overwrite anything.
                existing_history = source_data.get('price_history', [])

                # 2. Update the source data with all the new information from the importer.
                current_price = approved_prod.get('new_sale_price') or approved_prod.get('new_regular_price')
                source_data.update({
                    "product_id": approved_prod.get(f'{source}_id'),
                    "sale_price": approved_prod.get('new_sale_price'),
                    "regular_price": approved_prod.get('new_regular_price'),
                    "affiliate_url": approved_prod.get('affiliate_link'),
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                    "stock_status": approved_prod.get('stock_status', 'in_stock')
                })

                # 3. Now, append the new price to the history we saved in step 1.
                if current_price is not None:
                    # Prevents adding a new history entry if the price hasn't changed.
                    if not existing_history or (existing_history and existing_history[-1].get('price') != current_price):
                        existing_history.append({"date": today_str, "price": current_price})

                # 4. Save the fully updated history back into the source object.
                source_data['price_history'] = existing_history
                local_prod_to_update['linked_sources'][source] = source_data
                log_terminal("    - Step A: Complete.")

                log_terminal("    - Step B: Determining winning price...") # NEW LOG
                winning_source_key, lowest_price = None, float('inf')
                for source_key, data in local_prod_to_update.get('linked_sources', {}).items():
                    # This single, clean block ensures we only check in-stock products.
                    if data.get('stock_status') == 'in_stock':
                        price = data.get('sale_price') or data.get('regular_price')
                        if price is not None and price < lowest_price:
                            lowest_price = price
                            winning_source_key = source_key

                log_terminal(f"    - Step B: Complete. Winner is '{winning_source_key}' with price {lowest_price}.")
                
                if winning_source_key:
                    winning_source_data = local_prod_to_update['linked_sources'][winning_source_key]
                    
                    # --- STEP C: Update ALL fields in the local DB object ---
                    log_terminal("    - Step C: Updating local DB object in memory...")
                    # Update new-schema fields
                    local_prod_to_update.update({
                        "current_sale_price": winning_source_data.get('sale_price'),
                        "current_regular_price": winning_source_data.get('regular_price'),
                        "current_source": winning_source_key,
                        "current_affiliate_url": winning_source_data.get('affiliate_url')
                    })
                    
                    # Update legacy fields for perfect sync
                    shopee_data = local_prod_to_update.get('linked_sources', {}).get('shopee', {})
                    lazada_data = local_prod_to_update.get('linked_sources', {}).get('lazada', {})
                    local_prod_to_update.update({
                        "sale_price": winning_source_data.get('sale_price'),
                        "regular_price": winning_source_data.get('regular_price'),
                        "price_history": winning_source_data.get('price_history', []),
                        "shopee_id": shopee_data.get('product_id'),
                        "lazada_id": lazada_data.get('product_id'),
                        "external_url": winning_source_data.get('affiliate_url'),
                        "button_text": f"Get Lowest Price on {winning_source_key.capitalize()}"
                    })
                    log_terminal("    - Step C: Complete.")

                    # --- STEP D: Build the final WC API payload ---
                    log_terminal("    - Step D: Building WooCommerce API payload...")
                    win_sale, win_reg = winning_source_data.get('sale_price'), winning_source_data.get('regular_price')
                    final_sale_price_str = str(win_sale) if win_sale is not None else ""
                    final_reg_price_str = str(win_reg) if win_reg is not None else ""
                    final_main_price_str = final_sale_price_str or final_reg_price_str
                    
                    meta_data_list = []
                    for s_key, s_data in local_prod_to_update.get('linked_sources', {}).items():
                        meta_data_list.append({"key": f"_{s_key}_price", "value": str(s_data.get('sale_price') or s_data.get('regular_price') or "")})
                        meta_data_list.append({"key": f"_{s_key}_url", "value": str(s_data.get('affiliate_url') or "")})
                        meta_data_list.append({"key": f"_{s_key}_last_updated", "value": str(s_data.get('last_updated') or "")})
                        meta_data_list.append({"key": f"_{s_key}_price_history", "value": json.dumps(s_data.get('price_history', []))})

                    meta_data_list.append({"key": "_shopee_id", "value": str(shopee_data.get('product_id') or "")})
                    meta_data_list.append({"key": "_lazada_id", "value": str(lazada_data.get('product_id') or "")})
                    meta_data_list.append({"key": "_price_history", "value": json.dumps(winning_source_data.get('price_history', []))})

                    # --- V1.4 FIX: Re-introduce the audit log entry creation ---
                    price_before = previous_price
                    price_after = winning_source_data.get('sale_price') or winning_source_data.get('regular_price')
                    price_changed = not prices_match(price_before, price_after)

                    audit_entry = {
                        "name": local_prod_to_update.get('name'),
                        "wc_id": local_prod_to_update.get('id'),
                        "status": "Price Updated" if price_changed else "Synced",
                        "price_before": price_before,
                        "price_after": price_after,
                        "details": f"Winner: {winning_source_key.capitalize()}. All source data refreshed."
                    }
                    audit_log_entries.append(audit_entry)
                    # --- END FIX ---
                    
                    product_api_data = {
                        "id": local_prod_to_update.get('id'), "type": "external", "price": final_main_price_str,
                        "regular_price": final_reg_price_str, "sale_price": final_sale_price_str,
                        "external_url": winning_source_data.get('affiliate_url'), "button_text": f"Get Lowest Price on {winning_source_key.capitalize()}",
                        "meta_data": meta_data_list
                    }
                    wc_full_batch_payload.append(product_api_data)
                    log_terminal("    - Step D: Complete. Product added to the final sync batch.")
                else:
                    # --- NEW LOGIC: For when ALL sources are OUT OF STOCK ---
                    log_terminal(f"    - ⚠️ All sources for product ID {target_db_id} are out of stock. Setting to 'Phased Out' state.")

                    # Update local DB to reflect the phased-out state
                    local_prod_to_update.update({
                        "current_sale_price": None,
                        "current_regular_price": None,
                        "current_source": "none",
                        "current_affiliate_url": ""
                    })
                    # --- ADD THIS BLOCK ---
                    audit_entry = {
                        "name": local_prod_to_update.get('name'),
                        "wc_id": local_prod_to_update.get('id'),
                        "status": "Phased Out",
                        "price_before": previous_price,
                        "price_after": None,
                        "details": "All sources are out of stock. Product link updated to category page."
                    }
                    audit_log_entries.append(audit_entry)
                    # --- END BLOCK ---

                    # Prepare the special payload for WooCommerce
                    product_api_data = {
                        "id": local_prod_to_update.get('id'),
                        "price": "",          # Set price to empty
                        "regular_price": "",  # Set price to empty
                        "sale_price": "",     # Set price to empty
                        # Set the URL to the product's own permalink. The WP plugin will redirect this.
                        "external_url": "",
                        "button_text": "Out of Stock - Check Alternatives"
                    }
                    wc_full_batch_payload.append(product_api_data)
                    log_terminal("    - ✅ SUCCESS: 'Phased Out' product payload added to the batch.")
                    log_terminal("    - ⚠️ SKIPPING PAYLOAD: No winning price was determined.")
            else:
                 log_terminal(f"    - ❌ SKIPPING PRODUCT: No entry found in local database for ID {target_db_id}.") # NEW LOG

        # NEW LOG: Final check before API call
        log_terminal(f"--- Loop finished. Total products in final sync batch: {len(wc_full_batch_payload)} ---")

        if not wc_full_batch_payload:
            update_job_status("complete", "Sync complete. No products required an update.")
            return "Sync complete. No products required an update."

        # ...(The rest of the function remains the same)...
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

# --- Inspector and CLI tools (unchanged) ---
@celery_app.task(bind=True)
def inspect_wc_product_task(self, job_id: str, product_id: int):
    # This function remains unchanged
    log_terminal(f"--- [INSPECTOR TASK] Running live lookup for Product ID: {product_id} ---")
    wcapi = get_wc_api()
    if not wcapi:
        redis_client.set(job_id, json.dumps({"status": "failed", "error": "WooCommerce API not configured."}), ex=600)
        return
    try:
        response = wcapi.get(f"products/{product_id}")
        response.raise_for_status()
        product_data = response.json()
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
    # This function remains unchanged
    log_terminal(f"--- [COMMAND TOOL] Running live lookup for Product ID: {product_id} ---")
    wcapi = get_wc_api()
    if not wcapi:
        log_terminal("--- [COMMAND TOOL] FAILED: Cannot get WC API credentials.")
        return
    try:
        response = wcapi.get(f"products/{product_id}")
        response.raise_for_status()
        product_data = response.json()
        print("\n--- [COMMAND TOOL] SUCCESS: Full Live Product Data ---")
        print(json.dumps(product_data, indent=2))
        print("------------------------------------------------------\n")
    except requests.exceptions.RequestException as e:
        try:
            error_data = e.response.json()
            log_terminal(f"--- [COMMAND TOOL] FAILED: {e.response.status_code} Error ---")
            print(json.dumps(error_data, indent=2))
        except:
            log_terminal(f"--- [COMMAND TOOL] FAILED with a network or non-JSON error: {e} ---")
    except Exception as e:
         log_terminal(f"--- [COMMAND TOOL] FAILED with an unexpected error: {e} ---")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python data_tasks.py <product_id_to_check>")
        sys.exit(1)
    product_id_arg = sys.argv[1]
    run_inspector(product_id_arg)

@celery_app.task(bind=True)
def import_from_google_sheet_task(self, job_id: str, sheet_url: str, source: str):
    """
    (V2.0 - STOCK STATUS AWARE)
    Reads from "In Stock" and "Sold Out" tabs in a Google Sheet to assign a
    stock status to each product before staging it for review.
    """
    job_key = f"job:{job_id}"
    result_key = f"staging_area:{job_id}"
    log_terminal(f"--- [IMPORTER] Starting job {job_id} for source: {source.upper()} ---")
    
    try:
        # --- 1. Load Fresh DB & Build Lookup Maps (Your existing code) ---
        product_database = []
        try:
            with open(PRODUCT_DB_PATH, 'r', encoding='utf-8') as f:
                product_database = json.load(f)
        except Exception: pass
        
        shopee_id_map, lazada_id_map, name_map, all_product_names = {}, {}, {}, []
        for prod in product_database:
            if prod.get('shopee_id'): shopee_id_map[str(prod['shopee_id'])] = prod
            if prod.get('lazada_id'): lazada_id_map[str(prod['lazada_id'])] = prod
            if prod.get('name'):
                name_map[prod['name'].lower()] = prod
                all_product_names.append(prod['name'])
        
        # --- 2. Fetch Spreadsheet Metadata ---
        match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", sheet_url)
        spreadsheet_id = match.group(1)
        service = get_sheets_service()
        sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        
        staged_products = []
        
        # --- 3. NEW: Define Sheets to Process ---
        sheets_to_process = {
            "In Stock": "in_stock",
            "Sold Out": "out_of_stock"
        }

        # --- 4. NEW: Loop Through Each Sheet ---
        for sheet_name, stock_status in sheets_to_process.items():
            log_terminal(f"    - Searching for '{sheet_name}' sheet...")
            sheet = next((s for s in sheet_metadata['sheets'] if s['properties']['title'] == sheet_name), None)

            if not sheet:
                log_terminal(f"    - ⚠️ WARNING: Sheet named '{sheet_name}' not found. Skipping.")
                continue
            
            log_terminal(f"    - Found '{sheet_name}'. Fetching and parsing products...")
            grid_data = fetch_sheet_grid(spreadsheet_id, sheet_name)

            # --- 5. SOURCE-AWARE PROCESSING ROUTER (Your existing logic) ---
            if source == 'shopee':
                for row in grid_data:
                    vals = row.get("values", [])
                    if not vals or not vals[0].get("formattedValue"): continue
                    raw_text, url = extract_hyperlink_from_cell(vals[0])
                    if not url: continue
                    
                    cleaned_name = clean_product_name(raw_text)
                    slug = slugify(cleaned_name)
                    new_sale_price, new_regular_price = extract_prices_shopee(raw_text)
                    affiliate_link = convert_to_affiliate_link(url, slug)
                    ids = parse_ecommerce_url(url)
                    sheet_prod_id, sheet_shop_id, source_type = ids.get('product_id'), ids.get('shop_id'), ids.get('source')
                    button_text = f"Buy on {source_type.capitalize()}" if source_type else None
                    match, status, matched_by = None, "UNMATCHED", "unmatched"
                    if sheet_prod_id and source_type == 'shopee':
                        match = shopee_id_map.get(sheet_prod_id)
                    if match:
                        matched_by = "marketplace_id"
                    if not match:
                        match = name_map.get(cleaned_name.lower())
                        if match:
                            matched_by = "exact_name"
                    current_price, nearest_match_name = "N/A", None
                    if match:
                        status, current_price = "MATCHED", match.get('sale_price') or match.get('price', "N/A")
                        if matched_by == "marketplace_id": cleaned_name = match.get('name', cleaned_name)
                        slug = match.get('slug', slug)
                    else:
                        if all_product_names:
                            best_match = fuzz_process.extractOne(cleaned_name, all_product_names, scorer=fuzz.token_set_ratio)
                            if best_match: nearest_match_name = best_match[0]
                    
                    staged_products.append({
                        "slug": slug, "parsed_name": cleaned_name, "original_url": url, "affiliate_link": affiliate_link,
                        "new_sale_price": new_sale_price, "new_regular_price": new_regular_price, "button_text": button_text,
                        "status": status, "current_price": current_price, "nearest_match": nearest_match_name,
                        "shopee_id": sheet_prod_id, "lazada_id": None, "shop_id": sheet_shop_id, "source": source,
                        "matched_db_id": match.get('id') if match else None, "matched_db_slug": match.get('slug') if match else slug,
                        "matched_by": matched_by,
                        "stock_status": stock_status, # <-- TARGETED CHANGE
                    })

            elif source == 'lazada':
                row_iterator = iter(grid_data)
                for row in row_iterator:
                    vals = row.get("values", [])
                    if not vals or not vals[0].get("formattedValue"): continue
                    if vals[0].get("hyperlink"):
                        first_line_text, url = extract_hyperlink_from_cell(vals[0])
                        if not url: continue
                        price_lines = [v.get("formattedValue", "") for r in islice(row_iterator, 3) for v in r.get("values", [])]
                        cleaned_name = clean_product_name_lazada(first_line_text)
                        new_sale_price, new_regular_price = extract_prices_lazada(price_lines)
                        slug = slugify(cleaned_name)
                        affiliate_link = convert_to_affiliate_link(url, slug)
                        ids = parse_ecommerce_url(url)
                        sheet_prod_id, sheet_shop_id, source_type = ids.get('product_id'), ids.get('shop_id'), ids.get('source')
                        match, status, matched_by = None, "UNMATCHED", "unmatched"
                        if sheet_prod_id and source_type == 'lazada':
                            match = lazada_id_map.get(sheet_prod_id)
                        if match:
                            matched_by = "marketplace_id"
                        if not match:
                            match = name_map.get(cleaned_name.lower())
                            if match:
                                matched_by = "exact_name"
                        current_price, nearest_match_name = "N/A", None
                        if match:
                            status, current_price = "MATCHED", match.get('sale_price') or match.get('price', "N/A")
                            cleaned_name = match.get('name', cleaned_name)
                            slug = match.get('slug', slug)
                        else:
                            if all_product_names:
                                best_match = fuzz_process.extractOne(cleaned_name, all_product_names, scorer=fuzz.token_set_ratio)
                                if best_match: nearest_match_name = best_match[0]
                        
                        staged_products.append({
                            "slug": slug, "parsed_name": cleaned_name, "original_url": url, "affiliate_link": affiliate_link,
                            "new_sale_price": new_sale_price, "new_regular_price": new_regular_price, "button_text": "Buy on Lazada",
                            "status": status, "current_price": current_price, "nearest_match": nearest_match_name,
                            "shopee_id": None, "lazada_id": sheet_prod_id, "shop_id": sheet_shop_id, "source": source,
                            "matched_db_id": match.get('id') if match else None, "matched_db_slug": match.get('slug') if match else slug,
                            "matched_by": matched_by,
                            "stock_status": stock_status, # <-- TARGETED CHANGE
                        })

        # --- 6. Save to Redis (Your existing code) ---
        redis_client.set(result_key, json.dumps(staged_products), ex=3600)
        final_status = {"job_id": job_id, "status": "complete", "result_key": result_key, "message": f"Staged {len(staged_products)} products."}
        redis_client.set(job_key, json.dumps(final_status), ex=3600)

    except Exception as e:
        log_terminal(f"❌ [IMPORTER] FAILED for job {job_id}. Error: {e}")
        redis_client.set(
            job_key,
            json.dumps({
                "job_id": job_id,
                "status": "failed",
                "message": "Google Sheet import failed.",
                "error": str(e)
            }),
            ex=3600
        )
        raise e

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

# def run_bulk_add_news_tab(brand_name: str, tag_slug: str, limit: int = 0):
#     """
#     Finds products matching 'brand_name', appends a custom YIKES News tab,
#     and generates a JSON audit log of changes.
#     Args:
#         limit (int): If > 0, stops after processing this many products (for testing).
#     """
#     log_terminal(f"--- [BULK TAB TOOL] Starting News Tab Update for Brand: {brand_name} ---")
    
#     if limit > 0:
#         log_terminal(f"⚠️  TEST MODE ACTIVE: Limiting execution to first {limit} products.")

#     wcapi = get_wc_api()
#     if not wcapi:
#         return

#     # 1. Load Local DB
#     try:
#         with open(PRODUCT_DB_PATH, 'r', encoding='utf-8') as f:
#             local_products = json.load(f)
#     except:
#         log_terminal("❌ Error: Could not load local database.")
#         return

#     # Filter products
#     target_products = [p for p in local_products if brand_name.lower() in p['name'].lower()]
#     log_terminal(f"    - Found {len(target_products)} total matches for '{brand_name}'.")

#     # --- APPLY LIMIT ---
#     if limit > 0:
#         target_products = target_products[:limit]
#         log_terminal(f"    - processing subset of {len(target_products)} products...")

#     if not target_products:
#         return

#     updated_count = 0
#     audit_log = [] # List to store our log entries
    
#     # 2. Loop through targets
#     for index, prod in enumerate(target_products):
#         wc_id = prod['id']
#         name = prod['name']
#         permalink = prod.get('permalink') or prod.get('url') # Get URL for log
        
#         try:
#             # A. Fetch LIVE data
#             live_product = wcapi.get(f"products/{wc_id}").json()
#             meta_data = live_product.get('meta_data', [])

#             # B. Find existing YIKES tabs
#             yikes_tabs = []
#             for meta in meta_data:
#                 if meta['key'] == 'yikes_woo_products_tabs':
#                     yikes_tabs = meta['value']
#                     break
            
#             # C. Check duplicates
#             tab_exists = any(tag_slug in str(tab.get('content', '')) for tab in yikes_tabs)
#             if tab_exists:
#                 print(f"    - ⏭️  Skipping {name} (ID: {wc_id}) - Tab already exists.")
#                 continue

#             # D. Create New Tab
#             new_tab = {
#                 "title": f"📢 {brand_name} News and Updates",
#                 "id": f"{brand_name.lower()}-news-updates",
#                 "content": f'<p>[recent_posts_by_tax tag="{tag_slug}" show="6" columns="3" image="1" show_tags="0" show_cats="0"]</p>'
#             }

#             # E. Append & Send
#             yikes_tabs.append(new_tab)
#             payload = { "meta_data": [{ "key": "yikes_woo_products_tabs", "value": yikes_tabs }] }
            
#             wcapi.put(f"products/{wc_id}", payload).raise_for_status()
#             print(f"    - ✅ Updated {name} (ID: {wc_id})")
            
#             # --- F. Add to Audit Log ---
#             audit_log.append({
#                 "id": wc_id,
#                 "name": name,
#                 "url": permalink,
#                 "updated_at": datetime.now().isoformat()
#             })
            
#             updated_count += 1
#             time.sleep(0.5)

#         except Exception as e:
#             print(f"    - ❌ Failed to update {name}: {e}")

#     # 3. Save Audit Log to JSON File
#     if audit_log:
#         timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#         filename = f"audit_log_{brand_name}_{timestamp}.json"
#         try:
#             with open(filename, 'w', encoding='utf-8') as f:
#                 json.dump(audit_log, f, indent=2)
#             log_terminal(f"📄 Audit log saved to: {filename}")
#         except Exception as e:
#             log_terminal(f"⚠️ Failed to save audit log file: {e}")

#     log_terminal(f"--- [BULK TAB TOOL] Complete. Updated {updated_count} products. ---")

def run_bulk_add_news_tab(brand_name: str, tag_slug: str, limit: int = 0):
    """
    Finds products matching 'brand_name', appends a custom YIKES News tab
    with a specific SEO-optimized intro link, and generates a JSON audit log.
    """
    log_terminal(f"--- [BULK TAB TOOL] Starting News Tab Update for Brand: {brand_name} ---")
    
    # --- CONFIG: Dedicated News Page Mapping ---
    # Add your dedicated brand pages here. Keys must be lowercase.
    BRAND_NEWS_MAP = {
        "samsung": "https://gadgetph.com/smartphones/samsung/samsung-upcoming-releases-philippines-2025/", #docker-compose exec backend python data_tasks.py add_news "samsung" "samsung-news-updates" 1
        "xiaomi": "https://gadgetph.com/smartphones/xiaomi/xiaomi-upcoming-phones/", # docker-compose exec backend python data_tasks.py add_news "xiaomi" "iphone-news-updates" 1
        "apple": "https://gadgetph.com/smartphones/iphone/iphone-upcoming-releases/", #docker-compose exec backend python data_tasks.py add_news "apple" "iphone-news-updates" 1
        "realme": "https://gadgetph.com/smartphones/realme/realme-upcoming-phones/", # docker-compose exec backend python data_tasks.py add_news "realme" "realme-news-updates" 1
        "huawei": "https://gadgetph.com/smartphones/huawei/huawei-upcoming-phones/",
        "vivo": "https://gadgetph.com/smartphones/vivo/vivo-upcoming-phones/",
        # Add other brands here...
    }
    # -------------------------------------------

    if limit > 0:
        log_terminal(f"⚠️  TEST MODE ACTIVE: Limiting execution to first {limit} products.")

    wcapi = get_wc_api()
    if not wcapi:
        return

    # 1. Load Local DB
    try:
        with open(PRODUCT_DB_PATH, 'r', encoding='utf-8') as f:
            local_products = json.load(f)
    except:
        log_terminal("❌ Error: Could not load local database.")
        return

    # Filter products
    target_products = [p for p in local_products if brand_name.lower() in p['name'].lower()]
    log_terminal(f"    - Found {len(target_products)} total matches for '{brand_name}'.")

    if limit > 0:
        target_products = target_products[:limit]
        log_terminal(f"    - processing subset of {len(target_products)} products...")

    if not target_products:
        return

    updated_count = 0
    audit_log = [] 

    # 2. Loop through targets
    for index, prod in enumerate(target_products):
        wc_id = prod['id']
        name = prod['name']
        permalink = prod.get('permalink') or prod.get('url')
        
        try:
            # A. Fetch LIVE data
            live_product = wcapi.get(f"products/{wc_id}").json()
            meta_data = live_product.get('meta_data', [])

            # B. Find existing YIKES tabs
            yikes_tabs = []
            for meta in meta_data:
                if meta['key'] == 'yikes_woo_products_tabs':
                    # --- FIX: Ensure yikes_tabs is a list before using it ---
                    if isinstance(meta['value'], list):
                        yikes_tabs = meta['value']
                    else:
                        yikes_tabs = [] 
                    break
            
            # --- C. PREPARE CONTENT (Preserving your exact logic) ---
            target_tab_id = f"{brand_name.lower()}-news-updates"
            
            # 1. Determine Link Target
            target_url = BRAND_NEWS_MAP.get(brand_name.lower())
            if not target_url: target_url = f"/tag/{tag_slug}/"
            
            # 2. Build the SEO Intro
            # REFINED: Better flow that points "down" to the grid
            seo_intro = (
                f"<p>Stay updated on the latest <strong>{brand_name}</strong> price drops, "
                f"software rollouts, and new model releases in the Philippines. "
                f"Check out the trending stories below, or visit our dedicated "
                f'<a href="{target_url}" target="_blank" rel="noopener noreferrer"><strong>{brand_name} News & Updates</strong></a> page for full coverage.</p>'
            )
            
            # 3. Build Grid
            content_grid = f'[recent_posts_by_tax tag="{tag_slug}" show="6" columns="3" image="1" show_tags="0" show_cats="0"]'

            # 4. Wrap in Container
            final_html_content = f'<div class="brand-news-container">{seo_intro}{content_grid}</div>'
            
            # 5. Define Title
            new_title = f"📢 Latest {brand_name} News: Price Drops & Releases"

            # --- D. UPDATE or APPEND LOGIC (Replaces the 'Skip' logic) ---
            tab_found = False
            
            # Loop through existing tabs to see if we need to update one
            for tab in yikes_tabs:
                # Check if it's our tab (by ID) OR if it contains the shortcode (for older tabs without IDs)
                if tab.get('id') == target_tab_id or tag_slug in str(tab.get('content', '')):
                    # UPDATE the existing tab
                    tab['title'] = new_title
                    tab['id'] = target_tab_id # Enforce the correct ID
                    tab['content'] = final_html_content
                    print(f"    - 🔄 Updating existing tab for {name}...")
                    tab_found = True
                    break
            
            if not tab_found:
                # APPEND a new tab
                new_tab = {
                    "title": new_title,
                    "id": target_tab_id,
                    "content": final_html_content
                }
                yikes_tabs.append(new_tab)
                print(f"    - ➕ Appending new tab for {name}...")

            # E. Send Update
            payload = { "meta_data": [{ "key": "yikes_woo_products_tabs", "value": yikes_tabs }] }
            
            wcapi.put(f"products/{wc_id}", payload).raise_for_status()
            print(f"    - ✅ Success: {name} (ID: {wc_id})")
            
            # F. Add to Audit Log
            audit_log.append({
                "id": wc_id,
                "name": name,
                "url": permalink,
                "updated_at": datetime.now().isoformat()
            })
            
            updated_count += 1
            time.sleep(2.0)

        except Exception as e:
            print(f"    - ❌ Failed to update {name}: {e}")

    # 3. Save Audit Log
    if audit_log:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"audit_log_{brand_name}_{timestamp}.json"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(audit_log, f, indent=2)
            log_terminal(f"📄 Audit log saved to: {filename}")
        except Exception as e:
            log_terminal(f"⚠️ Failed to save audit log file: {e}")

    log_terminal(f"--- [BULK TAB TOOL] Complete. Updated {updated_count} products. ---")

# This special "if" block makes our file runnable as a script
# from the command line.
# This handles the command line arguments

# This handles the command line arguments
# This handles the command line arguments
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  1. Quick Inspect:     python data_tasks.py <product_id>")
        # print("  2. Search Categories: python data_tasks.py cats <search_term>")
        print("  3. Add News Tabs:     python data_tasks.py add_news <Brand> <Tag> [Limit]")
        print("  4. Explicit Inspect:  python data_tasks.py inspect <product_id>")
        sys.exit(1)
    
    command = sys.argv[1]

    # --- STRICT ROUTING LOGIC ---
    
    if command == "cats":
        # Disabled for now as requested
        pass

    elif command == "add_news":
        # Usage: python data_tasks.py add_news "Samsung" "samsung-news-updates" [1]
        if len(sys.argv) < 4:
            print("❌ Error: Please provide Brand Name and Tag Slug.")
            print('Example: python data_tasks.py add_news "Samsung" "samsung-news-updates" 1')
        else:
            brand_name = sys.argv[2]
            tag_slug = sys.argv[3]
            
            # Optional limit for testing
            limit = 0
            if len(sys.argv) > 4:
                try:
                    limit = int(sys.argv[4])
                except ValueError:
                    print("❌ Error: Limit must be an integer.")
                    sys.exit(1)
            
            run_bulk_add_news_tab(brand_name, tag_slug, limit)
            
    elif command == "inspect":
        # Explicit inspect command
        if len(sys.argv) < 3:
            print("❌ Error: Please provide a product ID.")
        else:
            run_inspector(sys.argv[2])

    elif command.isdigit():
        # Fallback: If the first argument is just a number, treat it as an ID check
        run_inspector(command)
        
    else:
        print(f"❌ Unknown command: '{command}'")
