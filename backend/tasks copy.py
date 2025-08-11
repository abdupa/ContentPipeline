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
from shared_state import redis_client, log_terminal
from celery.signals import worker_process_init
from urllib.parse import urljoin

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
<style>._scraper_selected{{outline:3px solid #f43f5e !important;box-shadow:0 0 15px rgba(244,63,94,.8);background-color:rgba(244,63,94,.2) !important}}._scraper_similar{{outline:2px dashed #3b82f6 !important;background-color:rgba(59,130,246,.15) !important}}</style><script>
    try {{
        const projectType = '{project_type}';
        let currentSelection = new Set();

        function getPreciseSelector(el) {{
            const path = []; let currentEl = el;
            while (currentEl && currentEl.nodeType === Node.ELEMENT_NODE) {{
                let selector = currentEl.nodeName.toLowerCase();
                if (currentEl.id && !/[0-9]/.test(currentEl.id)) {{
                    selector = '#' + currentEl.id; path.unshift(selector); break;
                }} else {{
                    let sib = currentEl, nth = 1;
                    while (sib = sib.previousElementSibling) {{
                        if (sib.nodeName.toLowerCase() == selector) nth++;
                    }}
                    if (nth != 1) selector += `:nth-of-type(${{nth}})`;
                }}
                path.unshift(selector); currentEl = currentEl.parentNode;
            }}
            return path.join(" > ");
        }}

        function getSmartSelector(el) {{
            if (!(el instanceof Element)) return;
            let parent = el;
            while (parent) {{
                if (parent.id && !/[0-9]/.test(parent.id)) return '#' + parent.id;
                const classList = Array.from(parent.classList);
                const descriptiveClasses = classList.filter(c => /(body|content|post|article|review|main)/i.test(c));
                if (descriptiveClasses.length > 0) return descriptiveClasses.map(c => '.' + c).join('');
                parent = parent.parentElement;
            }}
            return getPreciseSelector(el);
        }}

        function getSimilarSelector(el) {{
            const parent = el.parentElement;
            if (!parent || parent.children.length < 2) return null;
            const tagName = el.tagName;
            const classList = Array.from(el.classList).join('.');
            if (!classList) return null;
            const parentSelector = getPreciseSelector(parent);
            const potentialSelector = `${{parentSelector}} > ${{tagName}}.${{classList}}`;
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
             const capturedData = Array.from(elements).map(selector => {{
                const el = document.querySelector(selector);
                // For smart selectors, we need to pass the original selector
                return getElementData(el, selector);
            }}).filter(Boolean);
            console.log('[Scraper Debug] Sending message to parent:', {{ type: 'selection-updated', elements: capturedData }});
            window.parent.postMessage({{ type: 'selection-updated', elements: capturedData }}, '*');
        }}

        document.addEventListener('click', function(e) {{
            e.preventDefault(); e.stopPropagation();
            console.log(`[Scraper Debug] Click detected. Project Type: ${{projectType}}`);
            
            const targetEl = e.target;
            const isLink = targetEl.tagName === 'A' || targetEl.closest('a');

            // --- Smart Suggestion Logic (Only for links in phone scraper mode) ---
            if (projectType === 'phone_spec_scraper' && isLink) {{
                const similarSelector = getSimilarSelector(targetEl);
                if (similarSelector) {{
                    const allSimilarElements = Array.from(document.querySelectorAll(similarSelector));
                    allSimilarElements.forEach(el => el.classList.add('_scraper_similar'));
                    targetEl.classList.add('_scraper_selected');
                    
                    console.log('[Scraper Debug] Found similar links, sending suggestion.');
                    window.parent.postMessage({{
                        type: 'selection-suggestion',
                        single: getElementData(targetEl),
                        all: allSimilarElements.map(el => getElementData(el)).filter(Boolean),
                        count: allSimilarElements.length
                    }}, '*');
                    return; // Stop processing to wait for user choice
                }}
            }}

            // --- Standard Selection Logic ---
            let selector;
            if (projectType === 'phone_spec_scraper') {{
                selector = getPreciseSelector(targetEl);
                console.log('[Scraper Debug] Phone Scraper Mode - Precise Selector:', selector);
            }} else {{
                selector = getSmartSelector(targetEl);
                console.log('[Scraper Debug] Standard Article Mode - Smart Selector:', selector);
            }}
            
            if (!selector) return;

            // --- Toggle and Update Logic ---
            document.querySelectorAll('._scraper_selected').forEach(el => el.classList.remove('_scraper_selected'));

            if (projectType === 'phone_spec_scraper') {{
                // Multi-select for fields
                if (currentSelection.has(selector)) {{
                    currentSelection.delete(selector);
                }} else {{
                    currentSelection.add(selector);
                }}
            }} else {{
                // Single-select for standard articles
                currentSelection.clear();
                currentSelection.add(selector);
            }}
            
            currentSelection.forEach(sel => {{
                const el = document.querySelector(sel);
                if (el) el.classList.add('_scraper_selected');
            }});

            console.log('[Scraper Debug] Current Selection Set:', currentSelection);
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
def run_project_task(self, job_id: str, project_data: dict, target_date: str = None, limit: int = None):
    log_terminal(f"--- [RUNNER] Starting job {job_id} for project: {project_data.get('project_name')} ---")
    if target_date:
        log_terminal(f"    - Target date override: {target_date}")
    if limit:
        log_terminal(f"    - Article limit: {limit}")

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        context = browser.new_context(user_agent=random.choice(USER_AGENTS_LIST))
        page = context.new_page()

        try:
            job_status_json = redis_client.get(f"job:{job_id}")
            if not job_status_json: return
            job_status = json.loads(job_status_json)
            job_status['status'] = 'scraping'
            redis_client.set(f"job:{job_id}", json.dumps(job_status))
            
            config = project_data.get('scrape_config', {})
            initial_urls = config.get('initial_urls', [])
            
            article_links = []
            for url in initial_urls:
                page.goto(url, wait_until='domcontentloaded', timeout=60000)
                news_links_selector = "div.news-item > a"
                links = page.locator(news_links_selector).all()
                for link_locator in links:
                    href = link_locator.get_attribute('href')
                    if href:
                        full_url = urljoin(url, href)
                        article_links.append({"source_url": full_url})
            
            if limit and limit > 0:
                article_links = article_links[:limit]

            job_status['total_urls'] = len(article_links)
            redis_client.set(f"job:{job_id}", json.dumps(job_status))
            
            articles_to_process_count = 0
            for item in article_links:
                source_url = item['source_url']
                if redis_client.sismember(PROCESSED_URLS_KEY, source_url):
                    log_terminal(f"    - Skipping duplicate URL (already processed in a past run): {source_url}")
                    job_status_json = redis_client.get(f"job:{job_id}")
                    if job_status_json:
                        job_status = json.loads(job_status_json)
                        job_status['processed_urls'] += 1
                        redis_client.set(f"job:{job_id}", json.dumps(job_status))
                    continue

                page.goto(source_url, wait_until='domcontentloaded', timeout=60000)
                for rule in config.get('element_rules', []):
                    try:
                        page.locator(rule['selector']).first.wait_for(timeout=5000)
                        if rule['name'] == 'article_html':
                            item[rule['name']] = page.locator(rule['selector']).first.inner_html()
                        else:
                            item[rule['name']] = page.locator(rule['selector']).first.inner_text()
                    except Exception:
                        item[rule['name']] = None
                
                should_process = False
                date_str = item.get('date')

                if date_str:
                    article_dt = None
                    try:
                        article_dt = datetime.strptime(date_str, '%d %B %Y')
                    except ValueError:
                        article_dt = dateparser.parse(date_str)
                    
                    if article_dt:
                        article_dt = article_dt.replace(tzinfo=timezone.utc)
                        now_utc = datetime.now(timezone.utc)

                        if target_date:
                            filter_date = datetime.strptime(target_date, '%Y-%m-%d').date()
                            if article_dt.date() == filter_date:
                                should_process = True
                            else:
                                log_terminal(f"    - Skipping article, date {article_dt.date()} does not match target {filter_date}")
                        else:
                            if now_utc - article_dt < timedelta(days=2):
                                should_process = True
                            else:
                                log_terminal(f"    - Skipping article (older than 48 hours): {date_str}")
                    else:
                        log_terminal(f"    - Could not parse date, skipping: {date_str}")
                else:
                    log_terminal(f"    - No date found, skipping article.")
                
                if not should_process:
                    job_status_json = redis_client.get(f"job:{job_id}")
                    if job_status_json:
                        job_status = json.loads(job_status_json)
                        job_status['processed_urls'] += 1
                        redis_client.set(f"job:{job_id}", json.dumps(job_status))
                    continue
                
                articles_to_process_count += 1
                generate_content_from_template_task.delay(job_id, item, project_data['llm_prompt_template'])
            
            if articles_to_process_count == 0:
                final_job_status_json = redis_client.get(f"job:{job_id}")
                if final_job_status_json:
                    final_job_status = json.loads(final_job_status_json)
                    final_job_status['status'] = 'complete'
                    redis_client.set(f"job:{job_id}", json.dumps(final_job_status))
                    log_terminal(f"🎉 Job {job_id} finished. No new articles were found to process.")

        except Exception as e:
            log_terminal(f"❌ Critical error during scraping phase for job {job_id}: {e}")
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
def regenerate_content_task(self, draft_id: str):
    log_terminal(f"--- [RE-GENERATOR] Starting regeneration for draft: {draft_id} ---")
    draft_json = redis_client.get(f"draft:{draft_id}")
    if not draft_json:
        log_terminal(f"❌ Draft {draft_id} not found for regeneration.")
        return

    try:
        draft_data = json.loads(draft_json)
        scraped_data = draft_data.get("original_content", {})
        llm_prompt_template = draft_data.get("llm_prompt_template", "")

        if not scraped_data or not llm_prompt_template:
            log_terminal(f"❌ Draft {draft_id} is missing original content or prompt template.")
            return

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

        full_text_content = f"{scraped_data.get('title', '')}\n{scraped_data.get('article_html', '')}"
        mentioned_products = find_mentioned_products(full_text_content)
        related_products = find_related_products(mentioned_products, product_database)
        relevant_cluster = find_relevant_cluster(full_text_content)

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

        fields_to_update = [
            'focus_keyphrase', 'seo_title', 'meta_description', 'slug', 
            'post_category', 'post_tags', 'post_title', 'post_excerpt', 
            'featured_image_prompt', 'image_alt_text', 'image_title', 'post_content_html'
        ]
        for field in fields_to_update:
            if field in ai_json_response:
                draft_data[field] = ai_json_response[field]
        
        draft_data["generated_at"] = datetime.now(timezone.utc).isoformat()
        
        redis_client.set(f"draft:{draft_id}", json.dumps(draft_data))
        log_terminal(f"✅ Successfully regenerated and updated draft: {draft_id}")

    except Exception as e:
        log_terminal(f"❌ Error during content regeneration for {draft_id}: {e}")

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
        redis_client.set(f"draft:{draft_id}", json.dumps(draft_data))
        
        redis_client.set(f"job:{job_id}", json.dumps({"job_id": job_id, "status": "complete"}))
        log_terminal(f"✅ Successfully regenerated and updated image for draft: {draft_id}")

    except Exception as e:
        log_terminal(f"❌ Error during image regeneration for {draft_id}: {e}")
        redis_client.set(f"job:{job_id}", json.dumps({"job_id": job_id, "status": "failed", "error": str(e)}))
