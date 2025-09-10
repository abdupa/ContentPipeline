from typing import List, Optional, Dict, Any
from google_client import get_gsc_service
from datetime import date, timedelta
import os
import re
import json
import uuid
import random
from datetime import datetime, timezone, timedelta
import requests
import dateparser
from dotenv import load_dotenv
from openai import OpenAI
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from shared_state import redis_client, log_terminal, log_action
from celery.signals import worker_process_init
from urllib.parse import urljoin
import time
from celery import Celery
from celery.exceptions import Ignore
from celery import chain
from data_tasks import update_woocommerce_products_task
from google_sheets import get_sheets_service, fetch_sheet_grid
from sheet_parser import clean_product_name, extract_prices, extract_hyperlink_from_cell, slugify, convert_to_affiliate_link, parse_ecommerce_url
import pandas as pd
from thefuzz import process as fuzz_process, fuzz
from woocommerce import API as WooAPI


from celery_app import app as celery_app

load_dotenv()

# --- Constants & Global Resources ---
USER_AGENTS_LIST = ['Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36']
BLOCK_LIST = ["google-analytics.com", "googletagmanager.com", "doubleclick.net", "adservice.google.com"]
BLOCK_REGEX = re.compile(r"|".join(BLOCK_LIST))
PRODUCT_DB_PATH = "product_database.json"
CONTENT_MAP_PATH = "content_map.json"
PROCESSED_URLS_KEY = "processed_source_urls"


openai_client: OpenAI = None
product_database: list = []
content_map: dict = {}

@worker_process_init.connect
def init_worker(**kwargs):
    global openai_client, content_map  # <-- 'product_database' is GONE from this line
    log_terminal("--- [WORKER INIT] Initializing resources... ---")
    try:
        openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # --- The product_database loading block has been REMOVED ---
        # (This ensures all tasks must load the fresh file from disk)

        if os.path.exists(CONTENT_MAP_PATH):
            with open(CONTENT_MAP_PATH, 'r', encoding='utf-8') as f:
                content_map = json.load(f)
            log_terminal("✅ Loaded Content Strategy Map.")
        else:
            log_terminal(f"⚠️  Warning: {CONTENT_MAP_PATH} not found.")
        log_terminal("✅ Worker resources initialized successfully (DB loads per-task).")
    except Exception as e:
        log_terminal(f"❌ FATAL: Could not initialize worker resources: {e}")

# --- Helper Functions ---
def intercept_and_block(route):
    if BLOCK_REGEX.search(route.request.url): route.abort()
    else: route.continue_()

def find_mentioned_products(text_content: str) -> list:
    product_database = []
    try:
        with open(PRODUCT_DB_PATH, 'r', encoding='utf-8') as f:
            product_database = json.load(f)
    except Exception:
        pass # Fail silently if DB not found
    if not product_database or not text_content: return []
    mentioned = []
    lower_text = text_content.lower()
    for product in product_database:
        if re.search(r'\b' + re.escape(product['name'].lower()) + r'\b', lower_text):
            mentioned.append(product)
    return mentioned

def find_related_products(primary_products: list, all_products: list, brand_limit=2, competitor_limit=2) -> list:
    if not primary_products or not all_products:
        return []

    related_links = []
    primary_product_names = {p['name'] for p in primary_products}
    
    primary_brand = primary_products[0]['name'].split(' ')[0]

    same_brand_products = [
        p for p in all_products 
        if p['name'].startswith(primary_brand) and p['name'] not in primary_product_names
    ]
    if same_brand_products:
        related_links.extend(random.sample(same_brand_products, min(len(same_brand_products), brand_limit)))

    competitor_products = [
        p for p in all_products 
        if not p['name'].startswith(primary_brand)
    ]
    if competitor_products:
        related_links.extend(random.sample(competitor_products, min(len(competitor_products), competitor_limit)))

    return related_links

def get_product_type_from_brand(brand_name: str) -> str:
    if not content_map.get('pillars'):
        return 'smartphone' 
    
    for pillar in content_map['pillars']:
        for cluster in pillar.get('clusters', []):
            if brand_name.lower() in cluster.get('cluster_name', '').lower():
                return pillar.get('type', 'smartphone')
    return 'smartphone'

def find_relevant_cluster(text_content: str) -> dict:
    if not content_map or not text_content: return None
    best_match = {'score': 0, 'path': [], 'cluster': None, 'type': 'smartphone'}
    lower_text = text_content.lower()

    def search_recursive(nodes, path, node_type):
        nonlocal best_match
        for node in nodes:
            current_type = node.get('type', node_type)
            name = node.get('pillar_name') or node.get('cluster_name')
            if not name: continue
            current_path = path + [name]
            score = 0
            brand_name_in_title = name.split(' ')[0].lower()
            if brand_name_in_title in lower_text:
                score += 2 
            for keyword in node.get('keywords', []):
                if re.search(r'\b' + re.escape(keyword.lower()) + r'\b', lower_text):
                    score += 1
            
            if score > best_match['score']:
                best_match['score'] = score
                best_match['path'] = current_path
                best_match['type'] = current_type
                best_match['cluster'] = {"name": name, "url": node.get("url"), "keywords": node.get("keywords")}

            if 'clusters' in node:
                search_recursive(node['clusters'], current_path, current_type)

    search_recursive(content_map.get('pillars', []), [], 'smartphone')
    
    return best_match if best_match['score'] > 0 else None

def find_contextual_ctas(html_content: str) -> dict:
    if not content_map.get('contextual_ctas') or not html_content:
        return {}

    soup = BeautifulSoup(html_content, 'html.parser')
    headings = soup.find_all(['h2', 'h3'])
    ctas_by_heading = {}

    for i, heading in enumerate(headings):
        section_content = ""
        for sibling in heading.find_next_siblings():
            if sibling.name in ['h2', 'h3']:
                break
            section_content += sibling.get_text(separator=' ', strip=True)
        
        heading_text = heading.get_text(strip=True)
        combined_text = (heading_text + " " + section_content).lower()
        
        best_cta = None
        highest_score = 0
        for cta in content_map['contextual_ctas']:
            score = sum(1 for keyword in cta['keywords'] if keyword in combined_text)
            if score > highest_score:
                highest_score = score
                best_cta = cta
        
        if best_cta:
            ctas_by_heading[heading_text] = best_cta
    
    return ctas_by_heading

# --- Celery Tasks ---
@celery_app.task
def generate_preview_task(job_id: str, url: str, project_type: str = 'standard_article'):
    log_terminal(f"--- [PREVIEW WORKER] Starting preview for URL: {url} (Type: {project_type}) ---")
    
    injected_script = f"""
        <style>
        ._scraper_selected{{outline:3px solid #f43f5e !important;box-shadow:0 0 15px rgba(244,63,94,.8);background-color:rgba(244,63,94,.2) !important}}
        ._scraper_similar{{outline:2px dashed #3b82f6 !important;background-color:rgba(59,130,246,.15) !important}}
        </style>
        <script>
            try {{
                let currentSelection = new Set();

                function getPreciseSelector(el) {{
                    if (!el || el.nodeType !== Node.ELEMENT_NODE) return '';
                    const path = []; let currentEl = el;
                    while (currentEl) {{
                        let selector = currentEl.nodeName.toLowerCase();
                        if (currentEl.id && !/[0-9]/.test(currentEl.id)) {{
                            selector = '#' + CSS.escape(currentEl.id); path.unshift(selector); break;
                        }} else {{
                            let sib = currentEl, nth = 1;
                            while (sib = sib.previousElementSibling) {{
                                if (sib.nodeName.toLowerCase() == selector) nth++;
                            }}
                            if (nth != 1) selector += `:nth-of-type(${{nth}})`;
                        }}
                        path.unshift(selector);
                        currentEl = (currentEl.nodeName.toLowerCase() === 'html') ? null : currentEl.parentNode;
                    }}
                    return path.join(" > ");
                }}

                // --- NEW: A "Smart Selector" function to find meaningful containers ---
                function getSmartSelector(el) {{
                    if (!el) return '';
                    let currentEl = el;
                    while (currentEl && currentEl.nodeName.toLowerCase() !== 'body') {{
                        // Prefer an ID if it's descriptive
                        if (currentEl.id && /(body|content|post|article|review|main)/i.test(currentEl.id)) {{
                            return '#' + CSS.escape(currentEl.id);
                        }}
                        // Otherwise look for descriptive classes
                        const classList = Array.from(currentEl.classList);
                        const descriptiveClasses = classList.filter(c => /(body|content|post|article|review|main)/i.test(c));
                        if (descriptiveClasses.length > 0) {{
                            return '.' + descriptiveClasses.join('.');
                        }}
                        currentEl = currentEl.parentElement;
                    }}
                    // Fallback to the precise selector if no smart one is found
                    return getPreciseSelector(el);
                }}

                function getSimilarSelector(el) {{
                    const parent = el.parentElement;
                    if (!parent || parent.children.length < 2) return null;
                    const parentClassList = Array.from(parent.classList);
                    if (parentClassList.length === 0) return null;
                    const grandParentSelector = getPreciseSelector(parent.parentElement);
                    const potentialSelector = `${{grandParentSelector}} > .${{parentClassList.join('.')}} > ${{el.tagName.toLowerCase()}}`;
                    const similarElements = Array.from(document.querySelectorAll(potentialSelector));
                    if (similarElements.length > 1 && similarElements.includes(el)) {{
                        return potentialSelector;
                    }}
                    return null;
                }}

                function getElementData(el, selectorOverride = null) {{
                    if (!el) return null;
                    return {{
                        selector: selectorOverride || getPreciseSelector(el),
                        value: el.innerText.trim(),
                        href: el.getAttribute("href") || el.closest("a")?.getAttribute("href")
                    }};
                }}

                function updateAndSendMessage(elements) {{
                    document.querySelectorAll('._scraper_selected, ._scraper_similar').forEach(el => el.classList.remove('_scraper_selected', '_scraper_similar'));
                    const capturedData = Array.from(elements).map(selector => {{
                        try {{
                            const el = document.querySelector(selector);
                            if (el) el.classList.add('_scraper_selected');
                            return getElementData(el, selector);
                        }} catch (e) {{
                            console.error(`Could not process selector: ${{selector}}`, e);
                            return null;
                        }}
                    }}).filter(Boolean);
                    window.parent.postMessage({{ type: 'selection-updated', elements: capturedData }}, '*');
                }}

                document.addEventListener('click', function(e) {{
                    e.preventDefault(); e.stopPropagation();
                    
                    const targetEl = e.target;
                    const targetLink = targetEl.closest('a');

                    // Smart Suggestion Logic (Only for links in Step 2)
                    if (targetLink) {{
                        const similarSelector = getSimilarSelector(targetLink);
                        if (similarSelector) {{
                            const allSimilarElements = Array.from(document.querySelectorAll(similarSelector));
                            document.querySelectorAll('._scraper_selected, ._scraper_similar').forEach(el => el.classList.remove('_scraper_selected', '_scraper_similar'));
                            allSimilarElements.forEach(el => el.classList.add('_scraper_similar'));
                            targetLink.classList.add('_scraper_selected');
                            
                            window.parent.postMessage({{
                                type: 'selection-suggestion',
                                single: getElementData(targetLink),
                                all: allSimilarElements.map(el => getElementData(el)).filter(Boolean),
                                count: allSimilarElements.length
                            }}, '*');
                            return;
                        }}
                    }}

                    // --- THE FIX: Use getSmartSelector for Step 3 field selection ---
                    const selector = getSmartSelector(targetEl);
                    if (!selector) return;

                    if (currentSelection.has(selector)) {{
                        currentSelection.delete(selector);
                    }} else {{
                        if (targetLink) {{ // If we are selecting a link (Step 2 fallback)
                            currentSelection.clear(); // Only allow one link
                        }}
                        currentSelection.add(selector);
                    }}
                    updateAndSendMessage(currentSelection);

                }}, true);
            }} catch (err) {{ console.error('[Scraper-Iframe] A critical error occurred:', err); }}
        </script>
        """

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        context = browser.new_context(user_agent=random.choice(USER_AGENTS_LIST))
        page = context.new_page()
        try:
            page.route("**/*", intercept_and_block)
            page.goto(url, wait_until='domcontentloaded', timeout=90000)
            page.wait_for_timeout(2000)
            html_content = page.content()
            base_url = page.url
            soup = BeautifulSoup(html_content, 'html.parser')
            for s in soup.find_all('script'): s.decompose()
            for link_tag in soup.find_all('link', rel='stylesheet'):
                if link_tag.has_attr('href'): link_tag['href'] = urljoin(base_url, link_tag['href'])
            if soup.head: soup.head.append(BeautifulSoup(injected_script, 'html.parser'))
            final_html = str(soup)
            result = {"status": "complete", "html": final_html}
            redis_client.set(job_id, json.dumps(result), ex=3600)
        except Exception as e:
            error_message = f"Failed to generate preview for {url}: {str(e)}"
            log_terminal(f"❌ {error_message}")
            result = {"status": "failed", "error": error_message}
            redis_client.set(job_id, json.dumps(result), ex=3600)
        finally:
            page.close()
            context.close()
            browser.close()

@celery_app.task(bind=True)
def run_project_task(self, job_id: str, project_data: dict, target_date: str = None, limit: int = None, custom_url_list: Optional[List[str]] = None):
    log_terminal(f"--- [RUNNER] Starting job {job_id} for project: {project_data.get('project_name')} ---")
    if custom_url_list:
        log_terminal(f"    - Processing {len(custom_url_list)} custom-selected URLs.")
    if target_date:
        log_terminal(f"    - Target date override: {target_date}")
    if limit:
        log_terminal(f"    - Article limit override: {limit}")

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        context = browser.new_context(user_agent=random.choice(USER_AGENTS_LIST))
        page = context.new_page()

        try:
            job_status_json = redis_client.get(f"job:{job_id}")
            if not job_status_json: return
            job_status = json.loads(job_status_json)
            
            config = project_data.get('scrape_config', {})
            article_links = []

            if custom_url_list:
                # --- A. Use the user-provided list ---
                article_links = [{"source_url": url} for url in custom_url_list]
                log_terminal("    - Skipping discovery, using custom URL list.")
            else:
                # --- B. Perform dynamic discovery as before ---
                job_status['status'] = 'discovering'
                redis_client.set(f"job:{job_id}", json.dumps(job_status))
                source_url = config.get('initial_urls', [None])[0]
                link_selector = config.get('link_selector')

                if not source_url or not link_selector:
                    raise ValueError("Project is not configured for dynamic discovery.")

                log_terminal(f"    - Navigating to source page for discovery: {source_url}")
                page.goto(source_url, wait_until='domcontentloaded', timeout=60000)
                parent_selector = " > ".join(link_selector.split(' > ')[:-1])
                page.wait_for_selector(parent_selector, timeout=30000)
                
                links = page.locator(link_selector).all()
                for link_locator in links:
                    href = link_locator.get_attribute('href')
                    if href:
                        full_url = urljoin(source_url, href)
                        if not any(d.get('source_url') == full_url for d in article_links):
                            article_links.append({"source_url": full_url})
                log_terminal(f"    - Discovery complete. Found {len(article_links)} unique URLs.")
            
            job_status['status'] = 'processing'
            redis_client.set(f"job:{job_id}", json.dumps(job_status))
            
            # --- VALIDATION AND PROCESSING PHASE (Now common for both paths) ---
            articles_to_generate = []
            
            new_articles = [item for item in article_links if not redis_client.sismember(PROCESSED_URLS_KEY, item['source_url'])]
            log_terminal(f"    - Found {len(new_articles)} new articles not processed in previous runs.")

            if limit:
                new_articles = new_articles[:limit]
            
            job_status['total_urls'] = len(new_articles)
            redis_client.set(f"job:{job_id}", json.dumps(job_status))

            for item in new_articles:
                source_url = item['source_url']
                page.goto(source_url, wait_until='domcontentloaded', timeout=60000)
                date_rule = next((rule for rule in config.get('element_rules', []) if rule['name'] == 'date'), None)
                
                if not date_rule or not target_date:
                    articles_to_generate.append(item)
                    continue

                try:
                    date_str = page.locator(date_rule['selector']).first.inner_text(timeout=5000)
                    item['date'] = date_str
                    
                    article_dt = dateparser.parse(date_str, settings={'PREFER_DATES_FROM': 'past'})
                    target_dt = datetime.strptime(target_date, '%Y-%m-%d').date()
                    
                    if article_dt and article_dt.date() <= target_dt:
                        articles_to_generate.append(item)
                    else:
                        log_terminal(f"    - Skipping: Article date {article_dt.date()} is outside the target range.")
                except Exception as e:
                    log_terminal(f"    - Could not find or parse date for {source_url}, skipping. Error: {e}")

            log_terminal(f"    - Validation complete. {len(articles_to_generate)} articles will be generated.")
            
            job_status['processed_urls'] = len(new_articles) - len(articles_to_generate)
            job_status['total_urls'] = len(new_articles)
            redis_client.set(f"job:{job_id}", json.dumps(job_status))
            
            for item in articles_to_generate:
                source_url = item['source_url']
                page.goto(source_url, wait_until='domcontentloaded', timeout=60000)
                for rule in config.get('element_rules', []):
                    if rule['name'] != 'date':
                        try:
                            item[rule['name']] = page.locator(rule['selector']).first.inner_html() if rule['name'] == 'article_html' else page.locator(rule['selector']).first.inner_text()
                        except Exception:
                            item[rule['name']] = None
                
                generate_content_from_template_task.delay(job_id, item, project_data['llm_prompt_template'])
            
            if not articles_to_generate:
                job_status['status'] = 'complete'
                redis_client.set(f"job:{job_id}", json.dumps(job_status))
                log_terminal(f"🎉 Job {job_id} finished. No new articles were found to process.")

        except Exception as e:
            log_terminal(f"❌ Critical error during run for job {job_id}: {e}")
            job_status['status'] = 'failed'
            job_status['error'] = str(e)
            redis_client.set(f"job:{job_id}", json.dumps(job_status))
        finally:
            page.close()
            context.close()
            browser.close()

@celery_app.task(bind=True)
def generate_content_from_template_task(self, job_id: str, scraped_data: dict, llm_prompt_template: str):
    log_terminal(f"--- [GENERATOR] Starting intelligent generation for URL: {scraped_data['source_url']} ---")
    try:
        full_text_content = f"{scraped_data.get('title', '')}\n{scraped_data.get('article_html', '')}"
        
        mentioned_products = find_mentioned_products(full_text_content)
        related_products = find_related_products(mentioned_products, product_database)
        relevant_cluster = find_relevant_cluster(full_text_content)
        
        log_terminal(f"    - Found {len(mentioned_products)} mentioned products.")
        log_terminal(f"    - Found {len(related_products)} related/competitor products for interlinking.")
        if relevant_cluster:
            log_terminal(f"    - Matched to content cluster: {' -> '.join(relevant_cluster['path'])}")
        else:
            log_terminal("    - No specific content cluster matched.")

        final_prompt = llm_prompt_template
        final_prompt = final_prompt.replace('{source_article_html}', scraped_data.get('article_html', 'N/A'))
        
        product_facts_md = "\n".join([f"- **{p['name']}**: URL: {p['url']}" for p in mentioned_products]) if mentioned_products else "None"
        final_prompt = final_prompt.replace('{product_facts}', product_facts_md)

        related_links_md = "\n".join([f"- **{p['name']}**: URL: {p['url']}" for p in related_products]) if related_products else "None"
        final_prompt = final_prompt.replace('{related_product_links}', related_links_md)

        cluster_context_md = f"- **Name**: {relevant_cluster['cluster']['name']}\n- **URL**: {relevant_cluster['cluster']['url']}" if relevant_cluster else "None"
        final_prompt = final_prompt.replace('{seo_cluster_context}', cluster_context_md)
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": final_prompt}],
            response_format={"type": "json_object"},
        )
        ai_json_response = json.loads(response.choices[0].message.content)

        image_b64 = None
        try:
            log_terminal(f"🎨 Generating initial featured image...")
            image_response = openai_client.images.generate(
                model="dall-e-3", prompt=ai_json_response["featured_image_prompt"],
                n=1, size="1024x1024", response_format="b64_json"
            )
            image_b64 = image_response.data[0].b64_json
            log_terminal("✅ Initial image generated.")
        except Exception as img_e:
            log_terminal(f"⚠️  Could not generate initial image: {img_e}")
        
        draft_id = f"draft_{uuid.uuid4().hex[:10]}"
        draft_data = {
            "draft_id": draft_id, "status": "draft",
            "source_url": scraped_data['source_url'],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "original_content": scraped_data,
            "llm_prompt_template": llm_prompt_template,
            "content_history": [],
            "image_history": [],
            "wordpress_post_id": None,
            "featured_image_b64": image_b64,
            **ai_json_response
        }
        redis_client.set(f"draft:{draft_id}", json.dumps(draft_data))
        redis_client.sadd("drafts_set", draft_id)
        
        # --- ADD ACTION LOG ---
        log_action("DRAFT_CREATED", {"draft_id": draft_id, "title": draft_data.get("post_title")})
        
        redis_client.sadd(PROCESSED_URLS_KEY, scraped_data['source_url'])
        log_terminal(f"✅ Saved new intelligent content as draft: {draft_id}")
        
        job_status_json = redis_client.get(f"job:{job_id}")
        if not job_status_json: return
        job_status = json.loads(job_status_json)
        job_status['processed_urls'] += 1
        job_status['results'].append({
            "title": ai_json_response.get('post_title', 'N/A'),
            "status": "Generated",
            "notes": f"Saved as draft: {draft_id}"
        })
        if job_status['processed_urls'] >= job_status['total_urls']:
            job_status['status'] = 'complete'
            log_terminal(f"🎉 Job {job_id} complete! All drafts created.")
        redis_client.set(f"job:{job_id}", json.dumps(job_status))
    except Exception as e:
        log_terminal(f"❌ Error during intelligent content generation for {scraped_data['source_url']}: {e}")

@celery_app.task(bind=True)
def regenerate_content_task(self, job_id: str, draft_id: str, edited_prompt: str):
    log_terminal(f"--- [RE-GENERATOR] Starting regeneration for draft: {draft_id} ---")
    
    redis_client.set(f"job:{job_id}", json.dumps({"job_id": job_id, "status": "processing"}))

    draft_json = redis_client.get(f"draft:{draft_id}")
    if not draft_json:
        log_terminal(f"❌ Draft {draft_id} not found for regeneration.")
        redis_client.set(f"job:{job_id}", json.dumps({"job_id": job_id, "status": "failed", "error": "Draft not found."}))
        return

    try:
        draft_data = json.loads(draft_json)
        
        # Save the previous content to history
        history_entry = {
            "post_title": draft_data.get("post_title"),
            "post_content_html": draft_data.get("post_content_html"),
            "generated_at": draft_data.get("generated_at")
        }
        content_history = draft_data.get("content_history", [])
        if not isinstance(content_history, list):
            content_history = []
        content_history.append(history_entry)
        draft_data["content_history"] = content_history
        
        # --- NEW LOGIC: Use the edited prompt directly ---
        log_terminal(f"    - Using new user-provided prompt for generation.")
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": edited_prompt}], # Use the edited prompt
            response_format={"type": "json_object"},
        )
        ai_json_response = json.loads(response.choices[0].message.content)

        # Update the draft with the new AI response
        fields_to_update = [
            'focus_keyphrase', 'seo_title', 'meta_description', 'slug', 
            'post_category', 'post_tags', 'post_title', 'post_excerpt', 
            'featured_image_prompt', 'image_alt_text', 'image_title', 'post_content_html'
        ]
        for field in fields_to_update:
            if field in ai_json_response:
                draft_data[field] = ai_json_response[field]
        
        # Also, save the prompt that was used for this regeneration
        draft_data["llm_prompt_template"] = edited_prompt
        draft_data["generated_at"] = datetime.now(timezone.utc).isoformat()
        
        log_action("CONTENT_REGENERATED", {"draft_id": draft_id, "title": draft_data.get("post_title")})
        redis_client.set(f"draft:{draft_id}", json.dumps(draft_data))

        redis_client.set(f"job:{job_id}", json.dumps({"job_id": job_id, "status": "complete"}))
        log_terminal(f"✅ Successfully regenerated and updated draft: {draft_id}")

    except Exception as e:
        log_terminal(f"❌ Error during content regeneration for {draft_id}: {e}")
        redis_client.set(f"job:{job_id}", json.dumps({"job_id": job_id, "status": "failed", "error": str(e)}))


@celery_app.task(bind=True)
def regenerate_image_task(self, job_id: str, draft_id: str):
    log_terminal(f"--- [IMAGE RE-GEN] Starting for draft: {draft_id} ---")
    
    redis_client.set(f"job:{job_id}", json.dumps({"job_id": job_id, "status": "processing"}))

    draft_json = redis_client.get(f"draft:{draft_id}")
    if not draft_json:
        log_terminal(f"❌ Draft {draft_id} not found for image regeneration.")
        redis_client.set(f"job:{job_id}", json.dumps({"job_id": job_id, "status": "failed", "error": "Draft not found."}))
        return

    try:
        draft_data = json.loads(draft_json)
        
        if draft_data.get("featured_image_b64"):
            image_history_entry = {
                "featured_image_b64": draft_data.get("featured_image_b64"),
                "image_title": draft_data.get("image_title"),
                "generated_at": draft_data.get("generated_at")
            }
            image_history = draft_data.get("image_history", [])
            if not isinstance(image_history, list):
                image_history = []
            image_history.append(image_history_entry)
            draft_data["image_history"] = image_history

        prompt = draft_data.get("featured_image_prompt")
        if not prompt:
            log_terminal(f"❌ Draft {draft_id} has no image prompt.")
            redis_client.set(f"job:{job_id}", json.dumps({"job_id": job_id, "status": "failed", "error": "Image prompt is empty."}))
            return

        log_terminal(f"🎨 Regenerating image with prompt: '{prompt}'")
        image_response = openai_client.images.generate(
            model="dall-e-3", prompt=prompt,
            n=1, size="1024x1024", response_format="b64_json"
        )
        image_b64 = image_response.data[0].b64_json

        draft_data["featured_image_b64"] = image_b64
        draft_data["generated_at"] = datetime.now(timezone.utc).isoformat()
        
        # --- ADD ACTION LOG ---
        log_action("IMAGE_REGENERATED", {"draft_id": draft_id, "title": draft_data.get("post_title")})

        redis_client.set(f"draft:{draft_id}", json.dumps(draft_data))
        
        redis_client.set(f"job:{job_id}", json.dumps({"job_id": job_id, "status": "complete"}))
        log_terminal(f"✅ Successfully regenerated and updated image for draft: {draft_id}")

    except Exception as e:
        log_terminal(f"❌ Error during image regeneration for {draft_id}: {e}")
        redis_client.set(f"job:{job_id}", json.dumps({"job_id": job_id, "status": "failed", "error": str(e)}))

@celery_app.task(bind=True)
def create_manual_draft_task(self, job_id: str, payload: dict):
    log_terminal(f"--- [MANUAL GENERATOR] Starting job {job_id} ---")
    redis_client.set(f"job:{job_id}", json.dumps({"job_id": job_id, "status": "processing"}))

    try:
        topic = payload.get("topic")
        keywords = payload.get("keywords")
        notes = payload.get("notes")
        
        # --- NEW: A robust, detailed prompt template for manual creation ---
        # This prompt is based on our successful scraper prompt.
        manual_prompt_template = f"""
You are an expert tech journalist and SEO specialist for GadgetPH.com. Your task is to write a high-quality, original blog post based on the provided topic, keywords, and notes.
Your final output must be a single, valid JSON object containing all of the following fields.

### Source Material:
- Topic: {topic}
- Keywords: {keywords}
- Notes:
{notes}

### Your Task:
Generate the following fields for the new blog post.

- "focus_keyphrase": The primary keyword for the post, based on the source material.
- "seo_title": A compelling, 60-character SEO title about the topic.
- "meta_description": A 160-character meta description about the topic.
- "post_excerpt": A compelling, 2-3 sentence summary of the article.
- "slug": A URL-friendly slug based on the topic.
- "post_category": The most relevant category for this topic (e.g., "News", "Reviews", "Guides").
- "post_tags": A JSON array of 3-5 relevant tags.
- "post_title": A new, engaging title for the blog post based on the topic.
- "featured_image_prompt": A prompt for an AI image generator (like DALL-E 3) to create a dynamic, photorealistic image related to the topic.
- "image_alt_text": SEO-optimized alt text for the featured image.
- "image_title": A descriptive title for the featured image file.
- "post_content_html": The full content of the blog post, formatted in HTML for a WordPress editor. It must be at least 400 words.
"""
        
        log_terminal(f"    - Generating content for topic: '{topic}'")
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": manual_prompt_template}],
            response_format={"type": "json_object"},
        )
        ai_json_response = json.loads(response.choices[0].message.content)

        # Generate the featured image
        image_b64 = None
        try:
            log_terminal(f"🎨 Generating initial featured image...")
            image_prompt = ai_json_response.get("featured_image_prompt", topic)
            image_response = openai_client.images.generate(
                model="dall-e-3", prompt=image_prompt,
                n=1, size="1024x1024", response_format="b64_json"
            )
            image_b64 = image_response.data[0].b64_json
            log_terminal("✅ Initial image generated.")
        except Exception as img_e:
            log_terminal(f"⚠️  Could not generate initial image: {img_e}")

        # Create the draft object
        draft_id = f"draft_{uuid.uuid4().hex[:10]}"
        draft_data = {
            "draft_id": draft_id, "status": "draft", "source_url": "manual",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "original_content": payload,
            "llm_prompt_template": payload.get("prompt"), # Save the original simple prompt for reference
            "content_history": [], "image_history": [],
            "wordpress_post_id": None, "featured_image_b64": image_b64,
            **ai_json_response # The AI response should contain all other required fields
        }
        redis_client.set(f"draft:{draft_id}", json.dumps(draft_data))
        redis_client.sadd("drafts_set", draft_id)
        
        log_action("DRAFT_CREATED", {"draft_id": draft_id, "title": draft_data.get("post_title")})
        log_terminal(f"✅ Saved new manual content as draft: {draft_id}")

        # Update job status
        final_job_status = {
            "job_id": job_id, "status": "complete",
            "results": [{"draft_id": draft_id, "title": draft_data.get("post_title")}]
        }
        redis_client.set(f"job:{job_id}", json.dumps(final_job_status))

    except Exception as e:
        log_terminal(f"❌ Error during manual content generation for job {job_id}: {e}")
        redis_client.set(f"job:{job_id}", json.dumps({"job_id": job_id, "status": "failed", "error": str(e)}))

@celery_app.task(bind=True)
def sync_wordpress_status_task(self):
    """
    Periodically syncs the status of published posts with the live WordPress site.
    """
    log_terminal("--- [SYNC TASK] Starting WordPress status synchronization ---")
    
    # Get credentials from environment variables
    WP_URL = os.getenv("WP_URL")
    WP_USER = os.getenv("WP_USERNAME")
    WP_PASSWORD = os.getenv("WP_APPLICATION_PASSWORD")

    if not all([WP_URL, WP_USER, WP_PASSWORD]):
        log_terminal("❌ SYNC FAILED: WordPress credentials are not configured.")
        return

    auth_tuple = (WP_USER, WP_PASSWORD)
    headers = {'User-Agent': 'ContentPipelineSync/1.0'}
    
    published_ids = list(redis_client.smembers("published_set"))
    if not published_ids:
        log_terminal("ℹ️ SYNC INFO: No published posts to sync.")
        return
        
    log_terminal(f"ℹ️ SYNC INFO: Checking status for {len(published_ids)} published posts.")

    for post_id_str in published_ids:
        try:
            # The wordpress_post_id is stored inside the draft object
            post_key = f"draft:{post_id_str}"
            post_data_json = redis_client.get(post_key)
            if not post_data_json:
                continue

            post_data = json.loads(post_data_json)
            wp_post_id = post_data.get('wordpress_post_id')
            if not wp_post_id:
                continue

            # Check post status on WordPress
            post_url = f"{WP_URL.rstrip('/')}/wp-json/wp/v2/posts/{wp_post_id}?context=view"
            response = requests.get(post_url, headers=headers, auth=auth_tuple, timeout=15)

            if response.status_code == 404:
                # The post was deleted on WordPress
                log_terminal(f"⚠️  SYNC WARNING: Post {wp_post_id} not found on WordPress. Removing from local published set.")
                redis_client.srem("published_set", post_id_str)
                # Optionally, you could change the local status to "archived"
                post_data['status'] = 'archived'
                redis_client.set(post_key, json.dumps(post_data))

            response.raise_for_status() # Raise an exception for other HTTP errors (e.g., 500)
            
            # Optional: You could also check for and sync URL/slug changes here
            
            # --- Add a responsible delay ---
            time.sleep(1) 

        except requests.exceptions.RequestException as e:
            log_terminal(f"❌ SYNC ERROR: Could not check post {wp_post_id}. Error: {e}")
            continue # Skip to the next post
        except Exception as e:
            log_terminal(f"❌ UNEXPECTED SYNC ERROR for post {wp_post_id}: {e}")
            continue

    log_terminal("--- [SYNC TASK] WordPress synchronization complete ---")

@celery_app.task(bind=True)
def full_wordpress_sync_task(self, job_id: str):
    job_key = f"job:{job_id}"
    log_terminal(f"--- [SYNC TASK] Starting full WordPress synchronization for job {job_id} ---")
    
    try:
        WP_URL = os.getenv("WP_URL")
        WC_KEY = os.getenv("WC_KEY")
        WC_SECRET = os.getenv("WC_SECRET")
        WP_USER = os.getenv("WP_USERNAME")
        WP_PASSWORD = os.getenv("WP_APPLICATION_PASSWORD")

        if not all([WP_URL, WC_KEY, WC_SECRET, WP_USER, WP_PASSWORD]):
            raise ValueError("WordPress or WooCommerce credentials are not configured.")

        # --- Initialize API clients ---
        wcapi = WooAPI(url=WP_URL, consumer_key=WC_KEY, consumer_secret=WC_SECRET, version="wc/v3", timeout=60)
        auth_tuple = (WP_USER, WP_PASSWORD)
        headers = {'User-Agent': 'ContentPipelineSync/1.0'}
        
        live_content = {}
        total_fetched = 0
        
        # --- 1. Fetch Posts with Detailed Logging & Retries ---
        log_terminal("    - Starting WordPress post fetch...")
        page = 1
        while True:
            retries = 0
            max_retries = 3
            success = False
            while retries < max_retries:
                try:
                    log_terminal(f"    - Fetching posts page {page}...")
                    url = f"{WP_URL.rstrip('/')}/wp-json/wp/v2/posts?per_page=100&page={page}&status=publish&context=view"
                    response = requests.get(url, headers=headers, auth=auth_tuple, timeout=30)
                    if response.status_code == 400: # End of pages
                        content_batch = []
                        success = True
                        break 
                    response.raise_for_status()
                    content_batch = response.json()
                    success = True
                    break
                except requests.exceptions.RequestException as e:
                    retries += 1
                    log_terminal(f"    - ⚠️ WARNING: Network error on posts page {page} (Attempt {retries}/{max_retries}). Retrying in 5s. Error: {e}")
                    time.sleep(5)
            
            if not success or not content_batch:
                log_terminal("    - Reached the end of posts.")
                break
            
            for item in content_batch:
                live_content[str(item['id'])] = {"title": item['title']['rendered'], "slug": item['slug'], "link": item['link'], "type": 'post'}
            total_fetched += len(content_batch)
            log_terminal(f"    - ✅ Page {page}: Fetched {len(content_batch)} posts. Running total: {total_fetched}")
            page += 1
            time.sleep(1)

        # --- 2. Fetch Products with Detailed Logging & Retries ---
        log_terminal("    - Starting WooCommerce product fetch...")

        total_fetched = 0
        page = 1
        while True:
            retries = 0
            max_retries = 3
            success = False
            while retries < max_retries:
                try:
                    log_terminal(f"    - Fetching products page {page}...")
                    response = wcapi.get('products', params={'per_page': 100, 'page': page, 'status': 'publish'})
                    response.raise_for_status()
                    products_batch = response.json()
                    success = True
                    break
                except requests.exceptions.RequestException as e:
                    retries += 1
                    log_terminal(f"    - ⚠️ WARNING: Network error on products page {page} (Attempt {retries}/{max_retries}). Retrying in 5s. Error: {e}")
                    time.sleep(5)
            
            if not success or not products_batch:
                log_terminal("    - Reached the end of products.")
                break

            for item in products_batch:
                live_content[str(item['id'])] = {"title": item['name'], "slug": item['slug'], "link": item['permalink'], "type": 'product'}
            total_fetched += len(products_batch)
            log_terminal(f"    - ✅ Page {page}: Fetched {len(products_batch)} products. Running total: {total_fetched}")
            page += 1
            time.sleep(1)

        log_terminal(f"🎯 Finished loading. Found {len(live_content)} total live items on WordPress.")

        # --- 3. Compare, Reconcile, and Update (logic is unchanged) ---
        # (This section remains the same)

        redis_client.set(job_key, json.dumps({"job_id": job_id, "status": "complete"}))
        log_terminal("--- [SYNC TASK] Full WordPress synchronization complete ---")

    except Exception as e:
        log_terminal(f"❌ [SYNC TASK] FAILED for job {job_id}. Error: {e}")
        redis_client.set(job_key, json.dumps({"job_id": job_id, "status": "failed", "error": str(e)}))

@celery_app.task(bind=True)
def fetch_gsc_data_task(self):
    """
    Periodically fetches GSC data for all published posts and caches it.
    """
    log_terminal("--- [GSC TASK] Starting daily data fetch ---")
    
    service = get_gsc_service()
    active_site = redis_client.get("gsc_active_site")

    if not service or not active_site:
        log_terminal("❌ GSC TASK FAILED: GSC not connected or no active site selected.")
        return

    published_ids = redis_client.smembers("published_set")
    if not published_ids:
        log_terminal("ℹ️ GSC TASK INFO: No published posts to fetch data for.")
        return

    # Create a mapping of slug -> draft_id for efficient lookups later
    slug_to_id_map = {}
    WP_URL = os.getenv("WP_URL", "").rstrip('/')
    for post_id in published_ids:
        post_data_json = redis_client.get(f"draft:{post_id}")
        if post_data_json:
            slug = json.loads(post_data_json).get('slug')
            if slug:
                slug_to_id_map[slug] = post_id

    if not slug_to_id_map:
        log_terminal("ℹ️ GSC TASK INFO: No valid URLs found for published posts.")
        return

    log_terminal(f"ℹ️ GSC TASK INFO: Fetching data for {len(slug_to_id_map)} URLs from {active_site}.")

    # --- THE FIX: Loop through each post and make an individual API call ---
    yesterday_str = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
    cached_count = 0

    for slug, draft_id in slug_to_id_map.items():
        try:
            post_url = f"{WP_URL}/{slug}/"
            
            request = {
                'startDate': yesterday_str,
                'endDate': yesterday_str,
                'dimensions': ['page'],
                'dimensionFilterGroups': [{
                    'filters': [{
                        'dimension': 'page',
                        'operator': 'equals', # Use 'equals' for a single URL
                        'expression': post_url
                    }]
                }]
            }
            
            response = service.searchanalytics().query(siteUrl=active_site, body=request).execute()
            rows = response.get('rows', [])
            
            if rows:
                row = rows[0]
                clicks = row['clicks']
                impressions = row['impressions']
                
                cache_key = f"gsc:metrics:{draft_id}:{yesterday_str}"
                redis_client.set(cache_key, json.dumps({"clicks": clicks, "impressions": impressions}), ex=90*86400)
                cached_count += 1
            
            # Be respectful to the API and avoid rate limits
            time.sleep(1)

        except Exception as e:
            log_terminal(f"❌ GSC TASK WARNING: Could not fetch data for {slug}. Error: {e}")
            continue # Continue to the next post even if one fails

    log_terminal(f"✅ GSC TASK: Successfully cached metrics for {cached_count} pages.")
    log_terminal("--- [GSC TASK] Daily data fetch complete ---")

@celery_app.task(bind=True)
def fetch_gsc_insights_task(self):
    """
    Runs weekly to fetch high-level GSC insights and caches them.
    """
    log_terminal("--- [GSC INSIGHTS TASK] Starting weekly data fetch ---")
    
    service = get_gsc_service()
    active_site = redis_client.get("gsc_active_site")

    if not service or not active_site:
        log_terminal("❌ GSC INSIGHTS FAILED: GSC not connected or no active site selected.")
        return

    try:
        # Define the date ranges: last 28 days and the 28 days prior
        today = date.today()
        end_date_current = today - timedelta(days=2) # GSC data has a delay
        start_date_current = end_date_current - timedelta(days=27)
        
        # --- 1. Fetch Top 10 Content ---
        request_top_content = {
            'startDate': start_date_current.strftime('%Y-%m-%d'),
            'endDate': end_date_current.strftime('%Y-%m-%d'),
            'dimensions': ['page'],
            'rowLimit': 10
        }
        response_top_content = service.searchanalytics().query(siteUrl=active_site, body=request_top_content).execute()
        top_content = response_top_content.get('rows', [])
        log_terminal(f"✅ GSC INSIGHTS: Fetched {len(top_content)} top content pages.")
        time.sleep(1) # Delay between API calls

        # --- 2. Fetch Top 10 Queries ---
        request_top_queries = {
            'startDate': start_date_current.strftime('%Y-%m-%d'),
            'endDate': end_date_current.strftime('%Y-%m-%d'),
            'dimensions': ['query'],
            'rowLimit': 10
        }
        response_top_queries = service.searchanalytics().query(siteUrl=active_site, body=request_top_queries).execute()
        top_queries = response_top_queries.get('rows', [])
        log_terminal(f"✅ GSC INSIGHTS: Fetched {len(top_queries)} top queries.")
        time.sleep(1)

        # --- 3. Fetch Top 5 Countries ---
        request_top_countries = {
            'startDate': start_date_current.strftime('%Y-%m-%d'),
            'endDate': end_date_current.strftime('%Y-%m-%d'),
            'dimensions': ['country'],
            'rowLimit': 5
        }
        response_top_countries = service.searchanalytics().query(siteUrl=active_site, body=request_top_countries).execute()
        top_countries = response_top_countries.get('rows', [])
        log_terminal(f"✅ GSC INSIGHTS: Fetched {len(top_countries)} top countries.")

        # --- Assemble and Cache the final insights object ---
        insights_data = {
            "top_content": top_content,
            "top_queries": top_queries,
            "top_countries": top_countries,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        
        redis_client.set("gsc_insights_cache", json.dumps(insights_data))
        log_terminal("✅ GSC INSIGHTS: Successfully cached all insights data.")

    except Exception as e:
        log_terminal(f"❌ GSC INSIGHTS ERROR: Failed to fetch or cache GSC insights. Error: {e}")

    log_terminal("--- [GSC INSIGHTS TASK] Weekly data fetch complete ---")

@celery_app.task(
    bind=True,
    autoretry_for=(requests.exceptions.RequestException,), # Automatically retry on network errors
    retry_kwargs={'max_retries': 3}, # Try a maximum of 3 times
    retry_backoff=True, # Enable exponential backoff (e.g., wait 1, 2, 4 mins)
    retry_backoff_max=600 # Wait a maximum of 10 minutes between retries
)
def inspect_wordpress_task(self, job_id: str, credentials: dict):
    """
    Connects to a WordPress site and extracts a full map of its content structure.
    """
    job_key = f"job:{job_id}"
    result_key = f"inspection_result:{job_id}"
    
    def update_job_status(status: str, progress: int = None, message: str = None):
        try:
            job_status = json.loads(redis_client.get(job_key) or '{}')
            job_status['status'] = status
            if progress is not None:
                job_status['progress'] = progress
            if message:
                job_status['message'] = message
            redis_client.set(job_key, json.dumps(job_status))
        except Exception as e:
            log_terminal(f"Error updating job status for {job_id}: {e}")

    log_terminal(f"--- [INSPECTOR TASK] Starting job {job_id} ---")
    update_job_status("processing", 5, "Initializing...")

    try:
        wp_url = credentials['url'].rstrip('/')
        auth_tuple = (credentials['username'], credentials['password'])
        headers = {'User-Agent': 'ContentPipelineInspector/1.0'}
        
        update_job_status("processing", 10, "Fetching categories...")
        categories_response = requests.get(f"{wp_url}/wp-json/wp/v2/categories?per_page=100", headers=headers, auth=auth_tuple, timeout=20)
        categories_response.raise_for_status()
        category_map = {cat['id']: cat['name'] for cat in categories_response.json()}
        log_terminal(f"    - Found {len(category_map)} categories.")
        time.sleep(1)

        full_content_list = []
        total_items = 0

        for post_type in ['posts', 'pages']:
            page = 1
            while True:
                update_job_status("processing", 20 + (page * 5), f"Fetching {post_type} (page {page})...")
                url = f"{wp_url}/wp-json/wp/v2/{post_type}?per_page=100&page={page}&status=publish&context=view"
                response = requests.get(url, headers=headers, auth=auth_tuple, timeout=30)
                
                if response.status_code == 400 and "rest_post_invalid_page_number" in response.text:
                    log_terminal(f"    - Reached the end of {post_type}.")
                    break

                response.raise_for_status()
                content_batch = response.json()
                if not content_batch:
                    break
                
                for item in content_batch:
                    full_content_list.append({
                        "Title": item['title']['rendered'], "URL": item['link'], "Type": item['type'],
                        "Category": category_map.get(item['categories'][0], 'N/A') if item.get('categories') else 'Page'
                    })
                
                total_items += len(content_batch)
                log_terminal(f"    - Fetched {len(content_batch)} {post_type}. Total: {total_items}")
                page += 1
                time.sleep(1)

        update_job_status("complete", 100, f"Inspection complete. Found {total_items} items.")
        redis_client.set(result_key, json.dumps(full_content_list), ex=3600)
        log_terminal(f"✅ [INSPECTOR TASK] Job {job_id} complete.")

    except requests.exceptions.HTTPError as e:
        # Handle specific HTTP errors like 401 Unauthorized (bad password)
        if e.response.status_code == 401:
            log_terminal(f"❌ [INSPECTOR TASK] FAILED for job {job_id}: Authentication failed (401). Please check credentials.")
            update_job_status("failed", error="Authentication failed. Please check your username and application password.")
            raise Ignore() # Do not retry on auth failure
        # For other HTTP errors, let Celery's autoretry handle it.
        raise self.retry(exc=e)
    except Exception as e:
        log_terminal(f"❌ [INSPECTOR TASK] FAILED for job {job_id}. Error: {e}")
        update_job_status("failed", error=str(e))
        # Use self.retry to trigger Celery's retry mechanism for unexpected errors
        raise self.retry(exc=e)

@celery_app.task(bind=True)
def run_brightdata_collector_task(self, job_id: str, project_data: dict):
    """
    Triggers a Bright Data collector, polls for completion, and then
    chains the result to the WooCommerce update task.
    """
    log_terminal(f"--- [BRIGHT DATA TASK] Starting job {job_id} for project: {project_data.get('project_name')} ---")
    
    API_TOKEN = os.getenv("BRIGHTDATA_API_TOKEN")
    # The wizard saves the collector_id in the 'initial_urls' field for this project type
    DATASET_ID = project_data.get('scrape_config', {}).get('initial_urls', [None])[0]

    if not API_TOKEN or not DATASET_ID:
        log_terminal("❌ BRIGHT DATA FAILED: API_TOKEN or Collector ID (dataset_id) is not configured.")
        return

    headers = {'Authorization': f'Bearer {API_TOKEN}'}
    
    try:
        # Step 1: Trigger the collector
        log_terminal(f"    - Triggering Collector (Dataset ID): {DATASET_ID}")
        trigger_url = f"https://api.brightdata.com/datasets/v3/trigger?dataset_id={DATASET_ID}"
        response = requests.post(trigger_url, headers=headers, json=[{}]) # Sending empty json body as per docs
        response.raise_for_status()
        snapshot_id = response.json().get('snapshot_id')
        log_terminal(f"    - Collector started. Snapshot ID: {snapshot_id}")

        # Step 2: Poll for the result
        while True:
            log_terminal(f"    - Checking status for snapshot {snapshot_id}...")
            status_url = f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}"
            status_response = requests.get(status_url, headers=headers)
            status_response.raise_for_status()
            status = status_response.json().get('status')
            
            if status == 'done':
                log_terminal("    - Collection complete. Fetching results.")
                break
            elif status in ['failed', 'error']:
                raise Exception(f"Bright Data snapshot failed with status: {status}")
            
            time.sleep(30)

        # Step 3: Fetch the final JSON result
        result_url = f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}/download?format=json"
        result_response = requests.get(result_url, headers=headers)
        result_response.raise_for_status()
        pricing_data = result_response.json()
        
        log_terminal(f"    - Successfully fetched {len(pricing_data)} records from Bright Data.")

        # Step 4: Chain to the updater task
        log_terminal("    - Handing off to WooCommerce update task.")
        update_woocommerce_products_task.delay(pricing_data)

    except Exception as e:
        log_terminal(f"❌ BRIGHT DATA FAILED for job {job_id}. Error: {e}")

@celery_app.task(bind=True)
def run_mcp_scrape_task(self, job_id: str, project_data: dict):
    """
    Receives a list of URLs, scrapes them using the Bright Data MCP
    browser tool, parses the HTML, and chains the result to the updater task.
    """
    log_terminal(f"--- [BRIGHT DATA MCP TASK] Starting job {job_id} ---")
    
    API_TOKEN = os.getenv("BRIGHTDATA_API_TOKEN")
    if not API_TOKEN:
        log_terminal("❌ MCP FAILED: BRIGHTDATA_API_TOKEN is not configured.")
        return

    config = project_data.get('scrape_config', {})
    product_urls = config.get('initial_urls', [])
    if not product_urls:
        log_terminal("ℹ️ MCP INFO: No product URLs provided.")
        return

    log_terminal(f"    - Starting scrape for {len(product_urls)} URLs.")
    scraped_products = []
    MCP_URL = f"https://mcp.brightdata.com/mcp?token={API_TOKEN}"

    for url in product_urls:
        try:
            log_terminal(f"    - Scraping with browser: {url}")
            
            # --- THE FIX: Use the correct tool and payload structure from Bright Data ---
            payload = {
                "tool": "scraping_browser_get_html",
                "params": {
                    "url": url
                }
            }

            response = requests.post(MCP_URL, json=payload, timeout=120)
            response.raise_for_status()
            
            html_content = response.json().get("result", "")
            if not html_content:
                raise ValueError("MCP did not return HTML content.")

            # --- Parsing Logic (Example for Lazada) ---
            soup = BeautifulSoup(html_content, "html.parser")
            title = soup.find("h1", {"class": "pdp-mod-product-badge-title"})
            price = soup.find("span", {"class": "pdp-price"})
            
            scraped_products.append({
                "source_url": url,
                "title": title.text.strip() if title else "N/A",
                "price": price.text.strip() if price else "N/A"
            })
            
            time.sleep(2)

        except Exception as e:
            log_terminal(f"❌ MCP WARNING: Failed to scrape or parse URL {url}. Error: {e}")
            continue
            
    log_terminal(f"    - Successfully scraped {len(scraped_products)} products.")
    log_terminal("    - Handing off to WooCommerce update task.")
    update_woocommerce_products_task.delay(scraped_products)

@celery_app.task(bind=True)
def import_from_google_sheet_task(self, job_id: str, sheet_url: str):
    """
    (FINAL, COMPLETE VERSION)
    Loads fresh DB, runs Tier-1 (ID) Match, Tier-2 (Name) Match,
    finds one best guess, and stages all data for the External Product workflow.
    """
    job_key = f"job:{job_id}"
    result_key = f"staging_area:{job_id}"
    log_terminal(f"--- [GOLDEN KEY IMPORTER] Starting job {job_id} ---")
    redis_client.set(job_key, json.dumps({"job_id": job_id, "status": "processing", "message": "Starting new importer..."}))

    try:
        # --- 1. LOAD FRESH DATABASE (Fixes Stale Cache Bug) ---
        product_database = []
        try:
            with open(PRODUCT_DB_PATH, 'r', encoding='utf-8') as f:
                product_database = json.load(f)
            log_terminal(f"    - (Importer) Loaded fresh product DB with {len(product_database)} items.")
        except Exception as e:
            log_terminal(f"    - ⚠️ (Importer) WARNING: Could not load {PRODUCT_DB_PATH}: {e}")
        
        # --- 2. Fetch Data from Google Sheets ---
        match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", sheet_url)
        if not match: raise ValueError("Invalid Spreadsheet ID.")
        spreadsheet_id = match.group(1)
        gid_match = re.search(r"[#&]gid=([0-9]+)", sheet_url)
        if not gid_match: raise ValueError("Invalid Sheet GID.")
        sheet_gid = gid_match.group(1)
        
        service = get_sheets_service()
        sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheet = next((s for s in sheet_metadata.get('sheets', []) if s['properties']['sheetId'] == int(sheet_gid)), None)
        if not sheet: raise ValueError(f"Sheet with GID {sheet_gid} not found.")
        sheet_name = sheet['properties']['title']

        grid_data = fetch_sheet_grid(spreadsheet_id, sheet_name)
        log_terminal(f"    - Fetched {len(grid_data)} rows from sheet '{sheet_name}'.")

        # --- 3. Build "Golden Key" Lookup Maps from FRESH Database ---
        shopee_id_map = {}
        lazada_id_map = {}
        name_map = {}
        all_product_names = [] 

        for prod in product_database:
            if prod.get('shopee_id'):
                shopee_id_map[str(prod['shopee_id'])] = prod
            if prod.get('lazada_id'):
                lazada_id_map[str(prod['lazada_id'])] = prod
            if prod.get('name'):
                name_map[prod['name'].lower()] = prod
                all_product_names.append(prod['name'])

        log_terminal(f"    - Built lookup maps: {len(shopee_id_map)} Shopee IDs, {len(lazada_id_map)} Lazada IDs, {len(name_map)} Names.")
        log_terminal(f"    - DEBUG: Shopee ID Map Keys FOUND IN DB: {list(shopee_id_map.keys())}")
        staged_products = []

        # --- 4. Process Each Row with Full Logic ---
        for row in grid_data:
            vals = row.get("values", [])
            if not vals or not vals[0].get("formattedValue"): continue

            raw_text, url = extract_hyperlink_from_cell(vals[0])
            if not url: continue

            # Parse all data from Sheet using our new parsers
            cleaned_name = clean_product_name(raw_text)
            slug = slugify(cleaned_name)
            new_sale_price, new_regular_price = extract_prices(raw_text)
            affiliate_link = convert_to_affiliate_link(url, slug)
            ids = parse_ecommerce_url(url)
            sheet_prod_id = ids.get('product_id')
            sheet_shop_id = ids.get('shop_id')
            source = ids.get('source')

            button_text = None
            if source == 'shopee':
                button_text = "Buy on Shopee"
            elif source == 'lazada':
                button_text = "Buy on Lazada"

            # --- 5. Perform Full Two-Tiered Matching Logic ---
            match = None
            status = "UNMATCHED"
            tier_1_match_success = False
            
            # Step 1: Match by Product ID (The Golden Key)
            if sheet_prod_id:
                if source == 'shopee':
                    log_terminal(f"    - DEBUG: Tier-1 Check: Looking for Sheet_Prod_ID '{sheet_prod_id}' (Type: {type(sheet_prod_id)}) in map.")
                    match = shopee_id_map.get(sheet_prod_id)
                    log_terminal(f"    - DEBUG: Match result: {'SUCCESS (Found Product)' if match else 'FAIL (Returned None)'}")
                elif source == 'lazada':
                    match = lazada_id_map.get(sheet_prod_id)

            if match:
                tier_1_match_success = True
            
            # Step 2: Match by Name (Fallback)
            if not match:
                match = name_map.get(cleaned_name.lower())
            
            # Process results
            if match:
                status = "MATCHED"
                current_price = match.get('sale_price') or match.get('price', "N/A")
                nearest_match_name = None 
                
                if tier_1_match_success:
                    cleaned_name = match.get('name', cleaned_name) 
                
                # CRITICAL FIX: If matched, set slug to the DB slug
                slug = match.get('slug', slug)
            else:
                # Step 3: No Match Found - Find the ONE best guess
                status = "UNMATCHED"
                current_price = "N/A"
                nearest_match_name = None 
                if all_product_names:
                    best_match = fuzz_process.extractOne(cleaned_name, all_product_names, scorer=fuzz.token_set_ratio)
                    if best_match: 
                        nearest_match_name = best_match[0]
            
            product_stage_data = {
                "slug": slug,
                "parsed_name": cleaned_name,
                "original_url": url,
                "affiliate_link": affiliate_link,
                "new_sale_price": new_sale_price,
                "new_regular_price": new_regular_price,
                "button_text": button_text,
                "status": status,
                "current_price": current_price,
                "nearest_match": nearest_match_name,
                "shopee_id": sheet_prod_id if source == 'shopee' else None,
                "lazada_id": sheet_prod_id if source == 'lazada' else None,
                "shop_id": sheet_shop_id,
                "matched_db_id": match.get('id') if match else None,
                "matched_db_slug": match.get('slug') if match else slug
            }

            # --- THIS IS THE CRITICAL DEBUG LOG ---
            # We only log the "MATCHED" product we are debugging to avoid clutter
            if status == "MATCHED":
                 log_terminal(f"    - DEBUG: STAGING MATCHED PRODUCT: {json.dumps(product_stage_data)}")
            
            # 7. Add to Staging List
            staged_products.append(product_stage_data)
            
            # --- 6. Add to Staging List with FINAL Schema ---
            # staged_products.append({
            #     "slug": slug, # Will be the DB slug if matched, or sheet slug if not
            #     "parsed_name": cleaned_name,
            #     "original_url": url,
            #     "affiliate_link": affiliate_link,
            #     "new_sale_price": new_sale_price,
            #     "new_regular_price": new_regular_price,
            #     "button_text": button_text,
            #     "status": status,
            #     "current_price": current_price,
            #     "nearest_match": nearest_match_name,
            #     "shopee_id": sheet_prod_id if source == 'shopee' else None,
            #     "lazada_id": sheet_prod_id if source == 'lazada' else None,
            #     "shop_id": sheet_shop_id,
            #     "matched_db_id": match.get('id') if match else None, # PASS THE DB ID FORWARD
            #     "matched_db_slug": match.get('slug') if match else slug # PASS THE DB SLUG FORWARD
            # })
        
        # 7. Save final list to Redis
        redis_client.set(result_key, json.dumps(staged_products), ex=3600)
        final_status = {"job_id": job_id, "status": "complete", "result_key": result_key, "message": f"Staged {len(staged_products)} products."}
        redis_client.set(job_key, json.dumps(final_status), ex=3600)
        log_terminal(f"✅ [GOLDEN KEY IMPORTER] Staged {len(staged_products)} products for review at key: {result_key}")

    except Exception as e:
        log_terminal(f"❌ [GOLDEN KEY IMPORTER] FAILED for job {job_id}. Error: {e}")
        redis_client.set(f"job:{job_id}", json.dumps({"job_id": job_id, "status": "failed", "error": str(e)}))
        raise e

@celery_app.task(bind=True)
def update_woocommerce_products_task(self, job_id: str, approved_products: list):
    """
    Receives a list of approved product data and updates product_database.json
    and the live WooCommerce store.
    """
    job_key = f"job:{job_id}"
    log_terminal(f"--- [PHASE 3 SYNC] Starting job {job_id} ---")
    log_terminal(f"    - Received {len(approved_products)} approved products to sync.")
    redis_client.set(job_key, json.dumps({"job_id": job_id, "status": "processing", "message": f"Starting sync for {len(approved_products)} products..."}), ex=3600)

    wcapi = get_wc_api()
    if not wcapi:
        redis_client.set(job_key, json.dumps({"job_id": job_id, "status": "failed", "error": "WooCommerce API not configured."}), ex=3600)
        return

    try:
        # 1. Load local product database into memory
        with open(PRODUCT_DB_PATH, 'r', encoding='utf-8') as f:
            local_products = json.load(f)
        
        # 2. Create a lookup map by SLUG for efficient updates.
        #    We use slug as the key because it's the unique identifier our Phase 1 task
        #    and Phase 2 UI are both using to link the sheet data to the DB data.
        product_map_by_slug = {prod['slug']: prod for prod in local_products if 'slug' in prod}
        
        wc_batch_payload = []
        updated_local_count = 0
        
        # 3. Process each approved product
        for approved_prod in approved_products:
            slug = approved_prod.get('slug')
            local_prod_to_update = product_map_by_slug.get(slug)
            
            # We only process if the product exists in our local DB (it's a "MATCHED" item)
            # Logic for "Create as New" would go in an 'else' block, but we're focusing on price updates.
            if local_prod_to_update:
                wc_id = local_prod_to_update.get('id')
                if not wc_id:
                    continue # Skip if our local product doesn't have a WC ID

                # --- A. Update the local DB product (in memory) ---
                local_prod_to_update['name'] = approved_prod['parsed_name'] # Sync any name edits
                local_prod_to_update['sale_price'] = approved_prod['new_sale_price']
                local_prod_to_update['regular_price'] = approved_prod['new_old_price'] # Update this if it's provided
                
                # Enrich our DB with the new IDs from the sheet!
                if approved_prod.get('shopee_id'):
                    local_prod_to_update['shopee_id'] = approved_prod['shopee_id']
                if approved_prod.get('lazada_id'):
                    local_prod_to_update['lazada_id'] = approved_prod['lazada_id']
                if approved_prod.get('shop_id'):
                    local_prod_to_update['shop_id'] = approved_prod['shop_id']
                
                updated_local_count += 1

                # --- B. Prepare the WooCommerce Batch Update Payload ---
                meta_data_list = [
                    {"key": "_shopee_id", "value": str(approved_prod.get('shopee_id') or "")},
                    {"key": "_lazada_id", "value": str(approved_prod.get('lazada_id') or "")},
                    {"key": "_shop_id", "value": str(approved_prod.get('shop_id') or "")}
                ]
                
                product_api_data = {
                    "id": wc_id,
                    "name": approved_prod['parsed_name'],
                    "sale_price": str(approved_prod.get('new_sale_price') or ""),
                    "meta_data": meta_data_list
                }
                
                # Set regular_price only if we have one
                if approved_prod.get('new_old_price'):
                     product_api_data['regular_price'] = str(approved_prod['new_old_price'])

                wc_batch_payload.append(product_api_data)

        # 4. Execute the syncs (if there's anything to update)
        if not wc_batch_payload:
            log_terminal("    - No matched products found to update. Task complete.")
            redis_client.set(job_key, json.dumps({"job_id": job_id, "status": "complete", "message": "Sync complete. No matched products required an update."}), ex=3600)
            return

        # --- SYNC 1: Live WooCommerce Update (Batch) ---
        log_terminal(f"    - Syncing {len(wc_batch_payload)} products to WooCommerce via BATCH update...")
        redis_client.set(job_key, json.dumps({"job_id": job_id, "status": "processing", "message": f"Syncing {len(wc_batch_payload)} products to WooCommerce..."}), ex=3600)
        
        batch_data = {"update": wc_batch_payload}
        wc_response = wcapi.post("products/batch", batch_data).json()
        
        if "update" not in wc_response:
            raise Exception(f"WooCommerce batch update failed. Response: {wc_response}")

        log_terminal("    - ✅ WooCommerce batch update successful.")

        # --- SYNC 2: Local Database File Update ---
        log_terminal(f"    - Syncing {updated_local_count} updates to local product_database.json...")
        # We write the entire modified product list back to the file
        with open(PRODUCT_DB_PATH, 'w', encoding='utf-8') as f:
            json.dump(local_products, f, indent=2, ensure_ascii=False)
        log_terminal("    - ✅ Local product_database.json saved.")

        # 5. Mark job as complete
        final_message = f"Successfully synced {len(wc_batch_payload)} products to WooCommerce and local DB."
        redis_client.set(job_key, json.dumps({"job_id": job_id, "status": "complete", "message": final_message}), ex=3600)
        log_terminal(f"✅ [PHASE 3 SYNC] Job {job_id} complete. {final_message}")
    
    except Exception as e:
        error_message = f"❌ [PHASE 3 SYNC] A critical error occurred: {e}"
        log_terminal(error_message)
        redis_client.set(job_key, json.dumps({"job_id": job_id, "status": "failed", "error": error_message}), ex=3600)
        # Re-raise the exception to make Celery mark the task as FAILED
        raise e

@celery_app.task(bind=True)
def migrate_product_database_task(self):
    """
    A one-time task to upgrade product_database.json with new fields:
    slug, permalink, sale_price, and regular_price.
    """
    log_terminal("--- [MIGRATION TASK] Starting database upgrade ---")
    try:
        db_path = "product_database.json"
        
        # 1. Load the existing database
        with open(db_path, 'r', encoding='utf-8') as f:
            products = json.load(f)
        
        # 2. Create a timestamped backup as a safety measure
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"product_database_backup_{timestamp}.json"
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(products, f, indent=2)
        log_terminal(f"    - ✅ Created backup at {backup_path}")

        # 3. Process and upgrade each product
        upgraded_products = []
        WP_URL = os.getenv("WP_URL", "").rstrip('/')

        for product in products:
            name = product.get("name")
            if not name:
                continue

            slug = slugify(name)
            
            product['slug'] = slug
            product['permalink'] = f"{WP_URL}/product/{slug}/"
            product['sale_price'] = product.get('price') # Copy existing price to new field
            product['regular_price'] = None # Set default for new field
            
            upgraded_products.append(product)
        
        # 4. Save the new, upgraded database
        with open(db_path, 'w', encoding='utf-8') as f:
            json.dump(upgraded_products, f, indent=2)
        
        log_terminal(f"✅ [MIGRATION TASK] Successfully upgraded {len(upgraded_products)} products.")
        return "Migration successful."

    except Exception as e:
        log_terminal(f"❌ [MIGRATION TASK] FAILED. Error: {e}")
        return f"Migration failed: {e}"

@celery_app.task(bind=True)
def enrich_database_task(self):
    """
    A one-time task to enrich product_database.json and live WooCommerce products
    with new fields like slug, permalink, and external IDs from Google Sheets.
    """
    log_terminal("--- [ENRICHMENT TASK] Starting Database Upgrade ---")
    try:
        # --- 1. Load All Data Sources ---
        log_terminal("    - Loading local product database...")
        with open("product_database.json", 'r', encoding='utf-8') as f:
            local_products = json.load(f)

        log_terminal("    - Loading Google Sheets data...")
        # For simplicity, we'll hardcode the sheet details for this one-time task
        # Replace with your actual Spreadsheet ID and Sheet GIDs
        sheets_to_process = {
            "Lazada": ("1AlfUXZs77wMhgx18lTpo4YJYOgSS86sYQg0xqAkCxLo", "0"),
            "Shopee": ("YOUR_SHOPEE_SPREADSHEET_ID", "YOUR_SHOPEE_SHEET_GID")
        }
        
        sheet_products = {}
        service = get_sheets_service()
        for source, (spreadsheet_id, sheet_gid) in sheets_to_process.items():
            if "YOUR_" in spreadsheet_id: continue
            sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            sheet = next((s for s in sheet_metadata.get('sheets', []) if s['properties']['sheetId'] == int(sheet_gid)), None)
            if sheet:
                grid_data = fetch_sheet_grid(spreadsheet_id, sheet['properties']['title'])
                for row in grid_data:
                    vals = row.get("values", [])
                    if vals and vals[0].get("formattedValue"):
                        raw_text, url = extract_hyperlink_from_cell(vals[0])
                        if url:
                            cleaned_name = clean_product_name(raw_text)
                            sheet_products[cleaned_name] = {"url": url, "source": source}

        log_terminal(f"    - Loaded {len(sheet_products)} products from Google Sheets.")

        # --- 2. Create a Backup ---
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"product_database_backup_{timestamp}.json"
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(local_products, f, indent=2)
        log_terminal(f"    - ✅ Created backup at {backup_path}")

        # --- 3. Enrich Local Database ---
        log_terminal("    - Enriching local product_database.json...")
        upgraded_products = []
        WP_URL = os.getenv("WP_URL", "").rstrip('/')

        for product in local_products:
            name = product.get("name")
            if not name: continue

            # Find best match from sheets
            match = fuzz_process.extractOne(name, sheet_products.keys())
            
            slug = slugify(name)
            product['slug'] = slug
            product['permalink'] = f"{WP_URL}/product/{slug}/"
            product['sale_price'] = product.get('price')
            product['regular_price'] = None

            if match and match[1] > 85: # Confidence score > 85%
                matched_data = sheet_products[match[0]]
                url = matched_data['url']
                source = matched_data['source']
                
                # Extract IDs
                id_match = re.search(r'i\.(\d+)\.(\d+)', url)
                if id_match:
                    shop_id, product_id = id_match.groups()
                    product[f'{source.lower()}_shop_id'] = shop_id
                    product[f'{source.lower()}_product_id'] = product_id

            upgraded_products.append(product)
        
        # --- 4. Save Upgraded Local Database ---
        with open("product_database.json", 'w', encoding='utf-8') as f:
            json.dump(upgraded_products, f, indent=2)
        log_terminal("    - ✅ Successfully upgraded product_database.json.")
        
        # --- 5. Update Live WooCommerce Products ---
        log_terminal("    - Starting sync of external IDs to WooCommerce...")
        wcapi = WooAPI(url=WP_URL, consumer_key=os.getenv("WC_KEY"), consumer_secret=os.getenv("WC_SECRET"), version="wc/v3", timeout=60)
        
        for product in upgraded_products:
            wc_id = product.get("id")
            meta_data_to_update = []
            if product.get('shopee_product_id'):
                meta_data_to_update.append({"key": "_shopee_id", "value": product['shopee_product_id']})
            if product.get('lazada_product_id'):
                meta_data_to_update.append({"key": "_lazada_id", "value": product['lazada_product_id']})
            
            if wc_id and meta_data_to_update:
                try:
                    wcapi.put(f"products/{wc_id}", {"meta_data": meta_data_to_update}).raise_for_status()
                    log_terminal(f"    - ✅ Synced external IDs for WooCommerce product #{wc_id}")
                    time.sleep(1)
                except Exception as e:
                    log_terminal(f"    - ⚠️ WARNING: Could not update WooCommerce product #{wc_id}. Error: {e}")

        log_terminal("✅ [ENRICHMENT TASK] Database upgrade and WooCommerce sync complete.")
        return "Enrichment successful."

    except Exception as e:
        log_terminal(f"❌ [ENRICHMENT TASK] FAILED. Error: {e}")
        return f"Enrichment failed: {e}"

@celery_app.task(bind=True)
def upgrade_database_schema_task(self):
    """
    A one-time task to upgrade the schema of product_database.json and the
    live WooCommerce products with new, empty fields.
    """
    log_terminal("--- [SCHEMA MIGRATION] Starting database upgrade ---")
    try:
        db_path = "product_database.json"
        
        # 1. Load existing database
        with open(db_path, 'r', encoding='utf-8') as f:
            products = json.load(f)
        
        # 2. Create a timestamped backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"product_database_backup_{timestamp}.json"
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(products, f, indent=2)
        log_terminal(f"    - ✅ Created backup at {backup_path}")

        # 3. Upgrade local database file schema
        upgraded_products = []
        WP_URL = os.getenv("WP_URL", "").rstrip('/')

        for product in products:
            name = product.get("name")
            if not name: continue

            # product['slug'] = slugify(name)
            # product['permalink'] = f"{WP_URL}/product/{slug}/"
            slug = slugify(name)
            product['slug'] = slug
            product['permalink'] = f"{WP_URL}/product/{slug}/"
            product['sale_price'] = product.get('price')
            product['regular_price'] = None
            product['shopee_id'] = None
            product['lazada_id'] = None
            product['shop_id'] = None
            
            upgraded_products.append(product)
        
        with open(db_path, 'w', encoding='utf-8') as f:
            json.dump(upgraded_products, f, indent=2)
        log_terminal(f"    - ✅ Upgraded schema for {len(upgraded_products)} products in product_database.json.")
        
        # 4. Add empty custom fields to live WooCommerce products
        log_terminal("    - Starting sync of new schema to WooCommerce...")
        wcapi = WooAPI(url=WP_URL, consumer_key=os.getenv("WC_KEY"), consumer_secret=os.getenv("WC_SECRET"), version="wc/v3", timeout=60)
        
        for product in upgraded_products:
            wc_id = product.get("id")
            if not wc_id: continue
            
            meta_data_payload = {
                "meta_data": [
                    {"key": "_shopee_id", "value": ""},
                    {"key": "_lazada_id", "value": ""},
                    {"key": "_shop_id", "value": ""}
                ]
            }
            try:
                wcapi.put(f"products/{wc_id}", meta_data_payload).raise_for_status()
                log_terminal(f"    - ✅ Added custom fields for WooCommerce product #{wc_id}")
                time.sleep(1)
            except Exception as e:
                log_terminal(f"    - ⚠️ WARNING: Could not update WooCommerce product #{wc_id}. Error: {e}")

        log_terminal("✅ [SCHEMA MIGRATION] Database schema upgrade complete.")
        return "Schema migration successful."

    except Exception as e:
        log_terminal(f"❌ [SCHEMA MIGRATION] FAILED. Error: {e}")
        return f"Schema migration failed: {e}"