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
    global openai_client, product_database, content_map
    log_terminal("--- [WORKER INIT] Initializing resources... ---")
    try:
        openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        if os.path.exists(PRODUCT_DB_PATH):
            with open(PRODUCT_DB_PATH, 'r', encoding='utf-8') as f:
                product_database = json.load(f)
            log_terminal(f"✅ Loaded Product Database with {len(product_database)} products.")
        else:
            log_terminal(f"⚠️  Warning: {PRODUCT_DB_PATH} not found.")
        if os.path.exists(CONTENT_MAP_PATH):
            with open(CONTENT_MAP_PATH, 'r', encoding='utf-8') as f:
                content_map = json.load(f)
            log_terminal("✅ Loaded Content Strategy Map.")
        else:
            log_terminal(f"⚠️  Warning: {CONTENT_MAP_PATH} not found.")
        log_terminal("✅ Worker resources initialized successfully.")
    except Exception as e:
        log_terminal(f"❌ FATAL: Could not initialize worker resources: {e}")

# --- Helper Functions ---
def intercept_and_block(route):
    if BLOCK_REGEX.search(route.request.url): route.abort()
    else: route.continue_()

def find_mentioned_products(text_content: str) -> list:
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
def full_wordpress_sync_task(self):
    """
    Performs a full, two-way synchronization between the app's database and the live
    WordPress site, including both posts and WooCommerce products.
    """
    log_terminal("--- [SYNC TASK] Starting full WordPress synchronization ---")
    
    WP_URL = os.getenv("WP_URL")
    WP_USER = os.getenv("WP_USERNAME")
    WP_PASSWORD = os.getenv("WP_APPLICATION_PASSWORD")

    if not all([WP_URL, WP_USER, WP_PASSWORD]):
        log_terminal("❌ SYNC FAILED: WordPress credentials are not configured.")
        return

    auth_tuple = (WP_USER, WP_PASSWORD)
    headers = {'User-Agent': 'ContentPipelineSync/1.0'}
    
    live_content = {}
    
    # --- Step 1: Fetch all live content from WordPress ---
    for post_type in ['posts', 'products']:
        try:
            page = 1
            while True:
                url = f"{WP_URL.rstrip('/')}/wp-json/wp/v2/{post_type}?per_page=100&page={page}&status=publish&context=view"
                response = requests.get(url, headers=headers, auth=auth_tuple, timeout=30)
                response.raise_for_status()
                
                content_batch = response.json()
                if not content_batch:
                    break # No more content of this type
                
                for item in content_batch:
                    live_content[str(item['id'])] = {
                        "title": item['title']['rendered'],
                        "slug": item['slug'],
                        "link": item['link'],
                        "type": item['type'] # 'post' or 'product'
                    }
                
                log_terminal(f"ℹ️ SYNC INFO: Fetched page {page} of {post_type}.")
                page += 1
                time.sleep(5) # Be respectful to the server

        except requests.exceptions.RequestException as e:
            log_terminal(f"❌ SYNC ERROR: Could not fetch {post_type} from WordPress. Error: {e}")
            continue # Try the next post type if one fails

    log_terminal(f"✅ SYNC: Found {len(live_content)} total live items (posts and products) on WordPress.")

    # --- Step 2: Compare and Reconcile ---
    local_published_ids = {str(json.loads(redis_client.get(f"draft:{pid}")).get('wordpress_post_id')) for pid in redis_client.smembers("published_set")}
    live_ids = set(live_content.keys())

    # Posts to import (live on WP, not in our DB)
    ids_to_import = live_ids - local_published_ids
    # Posts to archive (in our DB, not live on WP)
    ids_to_archive = local_published_ids - live_ids

    log_terminal(f"ℹ️ SYNC: Found {len(ids_to_import)} new items to import and {len(ids_to_archive)} items to archive.")

    # --- Step 3: Perform Actions ---
    for wp_id in ids_to_import:
        item = live_content[wp_id]
        new_draft_id = f"draft_{uuid.uuid4().hex[:10]}"
        draft_data = {
            "draft_id": new_draft_id,
            "wordpress_post_id": int(wp_id),
            "status": "published",
            "source_url": item['link'],
            "post_title": item['title'],
            "slug": item['slug'],
            "draft_type": "woocommerce_product" if item['type'] == 'product' else 'wordpress_post',
            "generated_at": datetime.now(timezone.utc).isoformat(),
            # Add default empty values for other required fields
            "original_content": {"source": "Imported from WordPress"},
            "llm_prompt_template": "", "content_history": [], "image_history": [], "featured_image_b64": None,
            "focus_keyphrase": "", "seo_title": "", "meta_description": "", "post_category": "", "post_tags": [],
            "post_excerpt": "", "featured_image_prompt": "", "image_alt_text": "", "image_title": "", "post_content_html": ""
        }
        redis_client.set(f"draft:{new_draft_id}", json.dumps(draft_data))
        redis_client.sadd("published_set", new_draft_id)
        log_terminal(f"✅ SYNC: Imported new live content '{item['title']}'")

    for wp_id in ids_to_archive:
        # Find the draft by its WordPress ID
        for draft_id in redis_client.smembers("published_set"):
            post_data = json.loads(redis_client.get(f"draft:{draft_id}"))
            if str(post_data.get('wordpress_post_id')) == wp_id:
                post_data['status'] = 'archived'
                redis_client.set(f"draft:{draft_id}", json.dumps(post_data))
                redis_client.srem("published_set", draft_id)
                log_terminal(f"🗑️ SYNC: Archived post '{post_data.get('post_title')}' as it's no longer live.")
                break

    log_terminal("--- [SYNC TASK] Full WordPress synchronization complete ---")

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