import os
import re
import json
import uuid
import random
from datetime import datetime, timezone
import requests
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

def find_relevant_cluster(text_content: str) -> dict:
    if not content_map or not text_content: return None
    best_match = {'score': 0, 'path': [], 'cluster': None}
    lower_text = text_content.lower()
    def search_recursive(nodes, path):
        nonlocal best_match
        for node in nodes:
            name = node.get('pillar_name') or node.get('cluster_name')
            if not name: continue
            current_path = path + [name]
            score = 0
            for keyword in node.get('keywords', []):
                if re.search(r'\b' + re.escape(keyword.lower()) + r'\b', lower_text):
                    score += 1
            if score > best_match['score']:
                best_match['score'] = score
                best_match['path'] = current_path
                best_match['cluster'] = {"name": name, "url": node.get("url"), "keywords": node.get("keywords")}
            if 'clusters' in node:
                search_recursive(node['clusters'], current_path)
    search_recursive(content_map.get('pillars', []), [])
    return best_match if best_match['score'] > 0 else None

# --- Celery Tasks ---

@celery_app.task
def generate_preview_task(job_id: str, url: str):
    log_terminal(f"--- [PREVIEW WORKER] Starting preview job {job_id} for URL: {url} ---")
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        context = browser.new_context(user_agent=random.choice(USER_AGENTS_LIST))
        page = context.new_page()
        try:
            injected_script = """<style>._scraper_selected{outline:3px solid #f43f5e !important;box-shadow:0 0 15px rgba(244,63,94,.8);background-color:rgba(244,63,94,.2) !important}body{cursor:crosshair !important}</style><script>
                try {
                    const selectedElementPaths = new Set();
                    function getSmartSelector(el) {
                        if (!(el instanceof Element)) return;
                        if (el.tagName === 'P') {
                            let parent = el;
                            while (parent) {
                                if (parent.id && !/[0-9]/.test(parent.id)) { return '#' + parent.id; }
                                const classList = Array.from(parent.classList);
                                const descriptiveClasses = classList.filter(c => /(body|content|post|article|review|main)/i.test(c));
                                if (descriptiveClasses.length > 0) { return descriptiveClasses.map(c => '.' + c).join('');}
                                parent = parent.parentElement;
                            }
                        }
                        const path = [];
                        let currentEl = el;
                        while (currentEl && currentEl.nodeType === Node.ELEMENT_NODE) {
                            let selector = currentEl.nodeName.toLowerCase();
                            if (currentEl.id && !/[0-9]/.test(currentEl.id)) {
                                selector = '#' + currentEl.id;
                                path.unshift(selector);
                                break;
                            } else {
                                let sib = currentEl, nth = 1;
                                while (sib = sib.previousElementSibling) {
                                    if (sib.nodeName.toLowerCase() == selector) nth++;
                                }
                                if (nth != 1) selector += ":nth-of-type("+nth+")";
                            }
                            path.unshift(selector);
                            currentEl = currentEl.parentNode;
                        }
                        return path.join(" > ");
                    }
                    function updateAndSendMessage() {
                        const capturedData = Array.from(selectedElementPaths).map(selector => {
                            const el = document.querySelector(selector);
                            return el ? { selector, value: el.innerText.trim(), href: el.getAttribute("href") || el.closest("a")?.getAttribute("href") } : null;
                        }).filter(Boolean);
                        window.parent.postMessage({ type: 'selection-updated', elements: capturedData }, '*');
                    }
                    document.addEventListener('click', function(e) {
                        e.preventDefault(); e.stopPropagation();
                        const path = getSmartSelector(e.target);
                        if (!path) { return; }
                        const targetElement = document.querySelector(path);
                        if (!targetElement) return;
                        if (selectedElementPaths.has(path)) {
                            selectedElementPaths.delete(path);
                            targetElement.classList.remove('_scraper_selected');
                        } else {
                            selectedElementPaths.add(path);
                            targetElement.classList.add('_scraper_selected');
                        }
                        updateAndSendMessage();
                    }, true);
                } catch (err) { console.error('[Scraper-Iframe] A critical error occurred:', err); }
            </script>"""
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
            processed_urls_key = f"processed_urls:{project_data['project_id']}"
            redis_client.delete(processed_urls_key)
            
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
            
            for item in article_links:
                page.goto(item['source_url'], wait_until='domcontentloaded', timeout=60000)
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
                if target_date:
                    try:
                        filter_date = datetime.strptime(target_date, '%Y-%m-%d').date()
                        date_str = item.get('date')
                        if date_str:
                            article_date = datetime.strptime(date_str, '%d %B %Y').date()
                            if article_date == filter_date:
                                should_process = True
                            else:
                                log_terminal(f"    - Skipping article, date {article_date} does not match target {filter_date}")
                        else:
                            log_terminal(f"    - No date found, skipping article.")
                    except (ValueError, TypeError):
                        log_terminal(f"    - Could not parse date, skipping.")
                else:
                    date_str = item.get('date')
                    if date_str:
                        try:
                            article_date = datetime.strptime(date_str, '%d %B %Y').date()
                            today = datetime.now(timezone.utc).date()
                            if article_date == today:
                                should_process = True
                            else:
                                log_terminal(f"    - Skipping article from a different date: {date_str}")
                        except ValueError:
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
                
                if not redis_client.sismember(processed_urls_key, item['source_url']):
                    generate_content_from_template_task.delay(job_id, item, project_data['llm_prompt_template'])
                    redis_client.sadd(processed_urls_key, item['source_url'])
                else:
                    log_terminal(f"--- [RUNNER] Skipping duplicate URL: {item['source_url']} ---")
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
        relevant_cluster = find_relevant_cluster(full_text_content)
        log_terminal(f"    - Found {len(mentioned_products)} mentioned products.")
        if relevant_cluster:
            log_terminal(f"    - Matched to content cluster: {' -> '.join(relevant_cluster['path'])}")
        else:
            log_terminal("    - No specific content cluster matched.")
        final_prompt = llm_prompt_template
        final_prompt = final_prompt.replace('{title}', scraped_data.get('title', 'N/A'))
        final_prompt = final_prompt.replace('{article_html}', scraped_data.get('article_html', 'N/A'))
        final_prompt = final_prompt.replace('{source_url}', scraped_data.get('source_url', ''))
        product_facts_md = "\n".join([f"- **{p['name']}**: Price: {p['price']}, URL: {p['url']}" for p in mentioned_products]) if mentioned_products else "None"
        final_prompt = final_prompt.replace('{product_facts}', product_facts_md)
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
            "wordpress_post_id": None,
            "featured_image_b64": image_b64,
            **ai_json_response
        }
        redis_client.set(f"draft:{draft_id}", json.dumps(draft_data))
        redis_client.sadd("drafts_set", draft_id)
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
        relevant_cluster = find_relevant_cluster(full_text_content)
        final_prompt = llm_prompt_template
        final_prompt = final_prompt.replace('{title}', scraped_data.get('title', 'N/A'))
        final_prompt = final_prompt.replace('{article_html}', scraped_data.get('article_html', 'N/A'))
        final_prompt = final_prompt.replace('{source_url}', scraped_data.get('source_url', ''))
        product_facts_md = "\n".join([f"- **{p['name']}**: Price: {p['price']}, URL: {p['url']}" for p in mentioned_products]) if mentioned_products else "None"
        final_prompt = final_prompt.replace('{product_facts}', product_facts_md)
        cluster_context_md = f"- **Name**: {relevant_cluster['cluster']['name']}\n- **URL**: {relevant_cluster['cluster']['url']}" if relevant_cluster else "None"
        final_prompt = final_prompt.replace('{seo_cluster_context}', cluster_context_md)

        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": final_prompt}],
            response_format={"type": "json_object"},
        )
        ai_json_response = json.loads(response.choices[0].message.content)

        draft_data.update(ai_json_response)
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
        redis_client.set(f"draft:{draft_id}", json.dumps(draft_data))
        
        redis_client.set(f"job:{job_id}", json.dumps({"job_id": job_id, "status": "complete"}))
        log_terminal(f"✅ Successfully regenerated and updated image for draft: {draft_id}")

    except Exception as e:
        log_terminal(f"❌ Error during image regeneration for {draft_id}: {e}")
        redis_client.set(f"job:{job_id}", json.dumps({"job_id": job_id, "status": "failed", "error": str(e)}))
