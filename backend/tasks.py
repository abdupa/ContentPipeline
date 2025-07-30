import os
import re
import json
import random
from io import BytesIO
from datetime import datetime, timezone
import requests
from PIL import Image
from celery import Celery
from dotenv import load_dotenv
from openai import OpenAI, RateLimitError
from celery.exceptions import Ignore
from playwright.sync_api import sync_playwright, Playwright, Browser, Route 
from bs4 import BeautifulSoup
from shared_state import redis_client, log_terminal
from celery.signals import worker_process_init, worker_process_shutdown
from urllib.parse import urljoin



# --- CONFIGURATION & INITIALIZATION ---

# Load environment variables from .env file
load_dotenv()

# Define lists for rotation
USER_AGENTS_LIST = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15',
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0',
]

# PROXIES = ['180.190.10.223']

PROXIES = [
    '180.190.10.223', '192.126.159.96:8800', '173.232.7.217:8800',
    '38.153.36.92:8800', '104.206.59.102:8800', '173.208.39.161:8800',
]

# This list blocks most common ad, tracking, and analytics scripts.
BLOCK_LIST = [
    "google-analytics.com", "googletagmanager.com", "googlesyndication.com", "doubleclick.net",
    "adservice.google.com", "cdn.krxd.net", "ad.crwdcrtrl.net", "s.update.rubiconproject.com",
    "ads.pubmatic.com", "cdn.jsdelivr.net", "33across.com", "sync.min.js"
]

# A compiled regex for faster matching
BLOCK_REGEX = re.compile(r"|".join(BLOCK_LIST))

def _generalize_selector(selector: str) -> str:
    """
    Removes specific positional pseudo-classes like :nth-of-type() and :nth-child()
    from a CSS selector to make it more general.
    
    Example:
    Input:  '#review-body > ul > li:nth-of-type(16) > a'
    Output: '#review-body > ul > li > a'
    """
    # This regex finds :nth-of-type(...) or :nth-child(...) and removes it.
    generalized = re.sub(r':nth-(of-type|child)\([^)]+\)', '', selector)
    # Cleans up any trailing spaces left behind, e.g., 'li > a' -> 'li>a'
    generalized = re.sub(r'\s+>\s+', ' > ', generalized).strip()
    return generalized

def intercept_and_block(route: Route):
    """Aborts requests to domains in the BLOCK_LIST."""
    if BLOCK_REGEX.search(route.request.url):
        route.abort()
    else:
        route.continue_()


# --- CELERY & GLOBAL INSTANCE SETUP ---

celery_app = Celery("tasks", broker="redis://redis:6379/0", backend="redis://redis:6379/0")

# Global instances for OpenAI and Playwright to be managed by the worker lifecycle
openai_client: OpenAI = None
playwright_instance: Playwright = None
browser_instance: Browser = None

# --- NEW: WORKER LIFECYCLE MANAGEMENT USING STANDARD SIGNALS ---

@worker_process_init.connect
def init_worker(**kwargs):
    global openai_client, playwright_instance, browser_instance
    log_terminal("--- [WORKER INIT] Initializing resources... ---")
    try:
        openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        playwright_instance = sync_playwright().start()
        # Use a stealth script to avoid detection
        stealth_js_script = "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        # The browser is initialized here, it's the single source of truth
        browser_instance = playwright_instance.chromium.launch(args=["--no-sandbox"])
        log_terminal("✅ Worker resources initialized successfully.")
    except Exception as e:
        log_terminal(f"❌ FATAL: Could not initialize worker resources: {e}")


@worker_process_shutdown.connect
def shutdown_worker(**kwargs):
    global playwright_instance, browser_instance
    if browser_instance and not browser_instance.is_closed():
        browser_instance.close()
    if playwright_instance:
        playwright_instance.stop()
    log_terminal("--- [WORKER SHUTDOWN] Resources released. ---")


# --- NEW: MANUAL STEALTH SCRIPT ---
# This script hides the "webdriver" flag that automation tools set.
stealth_js_script = "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"


@celery_app.on_after_configure.connect
def setup_worker_instances(sender, **kwargs):
    """
    This function is triggered once when the worker starts.
    It initializes the OpenAI client and a single, persistent Playwright browser instance.
    """
    global openai_client, playwright_instance, browser_instance
    
    # Initialize OpenAI Client
    try:
        openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        log_terminal("✅ OpenAI client initialized successfully.")
    except Exception as e:
        log_terminal(f"❌ Error initializing OpenAI client: {e}")

    # Initialize Persistent Playwright Browser
    log_terminal("--- [WORKER STARTUP] Initializing persistent Playwright browser... ---")
    try:
        playwright_instance = sync_playwright().start()
        browser_instance = playwright_instance.chromium.launch(args=["--no-sandbox"])
        log_terminal("--- [WORKER STARTUP] Persistent browser launched successfully. ---")
    except Exception as e:
        log_terminal(f"--- [WORKER STARTUP] FATAL: Could not launch persistent browser: {e} ---")

# --- HELPER FUNCTIONS (For CSV Content Generation) ---

def generate_image_filename(title: str) -> str:
    """Creates a URL-friendly slug from a title."""
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    return slug

# ... (Your other existing helper functions like generate_image_tag, convert_openai_image_to_webp, 
#      and generate_post_content remain here without any changes) ...
def generate_image_tag(title: str, image_url: str) -> str:
    """Creates an HTML image tag with alt text."""
    alt = f"{title} – visual guide"
    return f'<img src="{image_url}" alt="{alt}" title="{alt}">'

def convert_openai_image_to_webp(image_url: str, row_data: dict):
    """(CORRECTED) Downloads, converts, and uploads an image using the REST API."""
    title = row_data.get("Post Title", "image")
    file_name = generate_image_filename(title) + ".webp"
    
    try:
        log_terminal(f"⬇️ Downloading DALL-E image...")
        # Step 1: Download image from OpenAI
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        image_bytes = response.content

        # Step 2: Convert to WebP in memory (THIS PART WAS MISSING)
        with Image.open(BytesIO(image_bytes)) as img:
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            
            img_resized = img.resize((1200, 675), Image.LANCZOS)
            
            webp_buffer = BytesIO()
            img_resized.save(webp_buffer, format="WEBP", quality=85)
            webp_buffer.seek(0)

        # Step 3: Upload to WordPress via REST API
        log_terminal(f"🚀 Uploading via REST API...")
        wp_api_url = f"{os.getenv('WP_URL')}/wp-json/wp/v2/media"
        headers = { 'User-Agent': 'Mozilla/5.0 ...', 'Content-Disposition': f'attachment; filename="{file_name}"', 'Content-Type': 'image/webp' }

        api_response = requests.post(
            wp_api_url,
            data=webp_buffer,
            headers=headers,
            auth=(os.getenv("WP_USERNAME"), os.getenv("WP_PASSWORD")),
            timeout=30
        )
        
        # New debugging block
        try:
            response_data = api_response.json()
        except json.JSONDecodeError:
            log_terminal(f"❌ JSON DECODE ERROR on image upload. Server responded with:")
            log_terminal(f"   Status Code: {api_response.status_code}")
            log_terminal(f"   Response Text: {api_response.text[:500]}") # Print first 500 chars
            raise # Re-raise the exception to fail the task

        api_response.raise_for_status()
        
        image_id = response_data['id']
        image_url_wp = response_data['source_url']
        
        log_terminal(f"✅ Image uploaded successfully. Media ID: {image_id}")
        return image_url_wp, image_id

    except Exception as e:
        log_terminal(f"❌ Failed during image conversion/upload: {e}")
        return None, None

def generate_post_content(row_data: dict) -> (str, int):
    """Generates blog post content using OpenAI based on a CSV row."""
    try:
        # Construct the detailed prompt from the row data
        prompt = f"""
Write a detailed, SEO-optimized blog post titled: “{row_data['Post Title']}”

Target the following keywords: {row_data["Primary Keywords"]}

Purpose: {row_data["Purpose"]}

Audience: US-based vehicle buyers and owners looking for VIN decoding, vehicle specs, and history reports.

Content Structure:
1. Introduction – Explain the topic and why it matters for used car research or ownership.
2. Main Sections – Break into logical H2/H3 headings. Include steps, bullet lists, or examples where helpful.
3. VIN Decoder Connection – Explain how this topic is relevant to decoding or checking a VIN.
4. Call to Action – Direct users to VinCheckPro’s free VIN decoder at https://www.vincheckpro.com/vindecoder/
5. Frequently Asked Questions (FAQ) – Add 3 to 5 common questions and concise, helpful answers related to the topic. Use <h3> for each question and <p> for the answer.
6. Ensure the final output is at least 1,000 words, highly informative, includes the FAQ section at the end, and is cleanly formatted using only the allowed HTML tags.

Formatting Requirements:
- The first paragraph must be a plain <p> element with no heading above it. Do not include any <h2>, <h3>, bold titles, or labels like "Introduction:" at the start of the article. It should open directly with a paragraph of content.
- Output only clean HTML compatible with the Divi theme.
- Use only semantic tags: <h2>, <h3>, <p>, <ul>, <ol>, <a href="">, <strong>, <em>.
- No emojis, no inline styles, and do not include <html>, <head>, or <body> tags.

Internal Linking Instructions:
- Naturally embed this link contextually in the first first paragraphs: <a href="{row_data['Homepage Internal Link']}">{row_data['Homepage Link Text']}</a>
- Naturally embed this link contextually in the second paragraphs: <a href="{row_data['Pillar Page Internal Link']}">{row_data['Pillar Link Text']}</a>
- Do NOT place internal links in a list or "See Also" format. Embed contextually.
- Ensure the final output is at least 1,000 words, highly informative, includes the FAQ section at the end, and is cleanly formatted using only the allowed HTML tags.
""".strip()

        print(f"Generating content for: {row_data['Post Title']}")
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert SEO content writer for the automotive industry."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=3500,
            timeout=90 # Use 'timeout' instead of 'request_timeout' in new API
        )
        content = response.choices[0].message.content.strip()
        # --- 2. Generate and Process Image ---
        image_prompt = row_data.get("Image Prompt", "").strip()
        if not image_prompt:
            log_terminal("⚠️ No image prompt found in CSV. Skipping image generation.")
            return content, None # Return content without an image ID

        log_terminal(f"🎨 Generating image with DALL-E 3...")
        image_response = openai_client.images.generate(
            model="dall-e-3",
            prompt=image_prompt,
            n=1,
            size="1792x1024", # 16:9 aspect ratio
            quality="standard"
        )
        image_url_raw = image_response.data[0].url

        # Use our new helper function to handle the image
        final_image_url, image_id = convert_openai_image_to_webp(image_url_raw, row_data)

        if not final_image_url:
            log_terminal("⚠️ Image processing failed. Proceeding without injecting image.")
            return content, image_id # Return content and any partial ID we might have

        # --- 3. Inject Image into Content (Optional) ---
        image_tag = generate_image_tag(row_data['Post Title'], final_image_url)
        # Injects the image after the first closing paragraph tag
        content = re.sub(r"(</p>)", r"\1\n\n" + image_tag, content, count=1, flags=re.IGNORECASE)
        
        log_terminal(f"✅ Successfully generated content and image ID: {image_id}")
        return content, image_id

    except Exception as e:
        log_terminal(f"❌ Critical error in generate_post_content: {e}")
        raise # Re-raise the exception to be caught by the Celery task

# --- CELERY TASKS ---

@celery_app.task(
    bind=True, autoretry_for=(RateLimitError,), retry_backoff=True,
    retry_kwargs={'max_retries': 3}, retry_backoff_max=60, rate_limit='4/m'
)

def process_single_row_task(self, job_id, row_data):
    """
    Final, robust task with proactive rate limiting, automatic retries,
    and detailed error notes.
    """
    title = row_data.get("Post Title", "No Title Provided")
    log_terminal(f"--- [WORKER] Starting job for: {title} ---")
    
    result_data = {}

    try:
        # --- This is your existing logic for generating content and publishing ---
        content, image_id = generate_post_content(row_data)
        
        # ... your existing logic to configure post options ...
        post_status = "draft"
        schedule_str = str(row_data.get("Schedule", "")).strip()
        if schedule_str:
            try:
                dt_obj = datetime.strptime(schedule_str, "%Y-%m-%d %H:%M:%S").isoformat()
                post_status = "future"
            except ValueError:
                dt_obj = None
                post_status = "draft"
        else:
            dt_obj = None

        post_data = {
            'title': title, 'content': content, 'status': post_status,
            'date': dt_obj, 'featured_media': image_id if image_id else 0,
        }

        # ... your existing logic to publish the post via REST API ...
        # (This part of your code is correct and doesn't need to change)
        wp_posts_url = f"{os.getenv('WP_URL')}/wp-json/wp/v2/posts"
        headers = { 'User-Agent': 'Mozilla/5.0 ...' }
        api_response = requests.post(wp_posts_url, json=post_data, headers=headers, auth=(os.getenv("WP_USERNAME"), os.getenv("WP_PASSWORD")), timeout=30)
        response_data = api_response.json()
        api_response.raise_for_status()
        post_url = response_data.get('link')
        # ----------------------------------------------------------------------

        # Data for a SUCCESSFUL post
        result_data = {
            "status": "Complete", "title": title, "actions": post_url,
            "post_status": response_data.get('status', 'Unknown').capitalize(),
            "generatedOn": datetime.now(timezone.utc).isoformat(),
            "notes": "Published successfully."
        }

    except RateLimitError as e:
        # This block now specifically handles the case where all retries have failed.
        log_terminal(f"--- [WORKER] FAILED job after retries for title: {title}, Error: Rate Limit ---")
        result_data = {
            "status": "Failed", "title": title, "actions": None, "post_status": "Failed",
            "generatedOn": datetime.now(timezone.utc).isoformat(),
            "notes": "OpenAI API rate limit hit. Task failed after multiple retries."
        }
        # This stops the task from being processed further after all retries are exhausted.
        raise Ignore()

    except Exception as e:
        # This block catches all other errors (like content policy violations).
        error_message = str(e)
        user_friendly_note = "An unexpected error occurred."

        # Creates specific notes for different types of failures.
        if "image_generation_user_error" in error_message:
            user_friendly_note = "Image prompt rejected by OpenAI policy."
        elif "timeout" in error_message:
            user_friendly_note = "Connection to an external service timed out."
        
        log_terminal(f"--- [WORKER] FAILED job for title: {title}, Error: {error_message} ---")
        
        result_data = {
            "status": "Failed", "title": title, "actions": None, "post_status": "Failed",
            "generatedOn": datetime.now(timezone.utc).isoformat(),
            "notes": user_friendly_note
        }

    # --- ATOMIC UPDATE LOGIC (remains the same) ---
    new_count = redis_client.incr(f"{job_id}:count")
    job_json = redis_client.get(job_id)
    if job_json:
        job = json.loads(job_json)
        job["results"].append(result_data)
        
        if new_count >= job["total_rows"]:
            job["status"] = "complete"
            log_terminal(f"🎉 All {new_count} tasks for job '{job_id}' are complete.")
        
        redis_client.set(job_id, json.dumps(job))
    
    return result_data

@celery_app.task
def generate_preview_task(job_id: str, url: str):
    """
    Creates a high-fidelity, responsive preview and generates STABLE CSS selectors
    by ignoring dynamic IDs.
    """
    global browser_instance
    if not browser_instance:
        log_terminal(f"❌ Preview job {job_id} failed: Persistent browser is not available.")
        return

    log_terminal(f"--- [PREVIEW WORKER] Starting HYBRID preview job {job_id} for URL: {url} ---")

    # --- UPDATED INJECTED SCRIPT ---
    injected_script = """
    <style>._scraper_selected{outline:3px solid #f43f5e !important;box-shadow:0 0 15px rgba(244,63,94,.8);background-color:rgba(244,63,94,.2) !important}body{cursor:crosshair !important}</style>
    <script>
        try {
            const log = (message, ...args) => console.log(`[Scraper-Iframe] ${message}`, ...args);
            const selectedElementPaths = new Set();

            function getUniqueCssSelector(el) {
                if (!(el instanceof Element)) return;
                const path = [];
                
                // --- NEW: Function to check for dynamic-looking IDs ---
                // A simple but effective check: if an ID contains a digit, we'll assume it's dynamic.
                const isDynamicId = (id) => /[0-9]/.test(id);

                while (el.nodeType === Node.ELEMENT_NODE) {
                    let selector = el.nodeName.toLowerCase();
                    
                    // --- UPDATED LOGIC ---
                    // Only use the ID if it exists AND it does NOT look dynamic.
                    if (el.id && !isDynamicId(el.id)) {
                        selector = '#' + el.id;
                        path.unshift(selector);
                        break; // ID is stable and unique, we can stop.
                    } else {
                        // If no stable ID, build path using nth-of-type
                        let sib = el, nth = 1;
                        while (sib = sib.previousElementSibling) {
                            if (sib.nodeName.toLowerCase() == selector)
                               nth++;
                        }
                        if (nth != 1) {
                            selector += ":nth-of-type("+nth+")";
                        }
                    }
                    path.unshift(selector);
                    el = el.parentNode;
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
                e.preventDefault();
                e.stopPropagation();
                const path = getUniqueCssSelector(e.target);
                if (!path) return;
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
        } catch (err) {
            console.error('[Scraper-Iframe] A critical error occurred:', err);
        }
    </script>
    """

    context = None
    page = None
    try:
        context = browser_instance.new_context(user_agent=random.choice(USER_AGENTS_LIST))
        page = context.new_page()
        page.route("**/*", intercept_and_block)
        page.goto(url, wait_until='domcontentloaded', timeout=90000)
        page.wait_for_timeout(2000)

        html_content = page.content()
        base_url = page.url 

        soup = BeautifulSoup(html_content, 'html.parser')
        for s in soup.find_all('script'):
            s.decompose()
        for link_tag in soup.find_all('link', rel='stylesheet'):
            if link_tag.has_attr('href'):
                link_tag['href'] = urljoin(base_url, link_tag['href'])
        if soup.head:
            soup.head.append(BeautifulSoup(injected_script, 'html.parser'))

        final_html = str(soup)

        result = {"status": "complete", "html": final_html}
        redis_client.set(job_id, json.dumps(result), ex=3600)
        log_terminal(f"--- [PREVIEW WORKER] Successfully generated HYBRID preview. ---")

    except Exception as e:
        error_message = f"Failed to generate preview for {url}: {str(e)}"
        log_terminal(f"❌ {error_message}")
        result = {"status": "failed", "error": error_message}
        redis_client.set(job_id, json.dumps(result), ex=3600)
    finally:
        if page and not page.is_closed():
            page.close()
        if context:
            context.close()

@celery_app.task
def scrape_website_task(job_id: str):
    """
    Performs a scrape based on the configuration from the wizard.
    Handles both 'direct' and 'crawl' type jobs with corrected logic.
    """
    global browser_instance
    if not browser_instance:
        log_terminal(f"❌ Scraper job {job_id} failed: Browser not available.")
        redis_client.set(job_id, json.dumps({"status": "failed", "error": "Browser not available."}))
        return

    log_terminal(f"--- [SCRAPER WORKER] Starting job: {job_id} ---")

    job_json = redis_client.get(job_id)
    if not job_json: return

    job_data = json.loads(job_json)
    config = job_data.get("config", {})
    
    page, context = None, None
    
    try:
        scrape_type = config.get("scrape_type")
        element_rules = config.get("element_rules", [])
        final_urls_to_scrape = []

        if scrape_type == 'direct':
            final_urls_to_scrape = config.get("modelUrls", [])

        elif scrape_type == 'crawl':
            # --- MODIFIED: Check for the new `final_urls` key first ---
            manual_final_urls = config.get("final_urls")
            if manual_final_urls:
                log_terminal("--- [CRAWLER] Found manually selected final URLs. Using them directly.")
                final_urls_to_scrape = manual_final_urls
            else:
                # Fallback to the old logic if needed (optional)
                log_terminal("--- [CRAWLER] No manually selected URLs found. Falling back to selector-based search.")
                # ... (old logic for finding links with a selector) ...

        if not final_urls_to_scrape:
            log_terminal(f"⚠️ [SCRAPER] Warning: Found 0 final pages to scrape.")
        else:
            log_terminal(f"✅ [SCRAPER] Found a total of {len(final_urls_to_scrape)} final pages to scrape.")
        
        # The rest of the scraping loop logic is correct and remains the same
        all_scraped_data = []
        job_data["total_urls"] = len(final_urls_to_scrape)
        redis_client.set(job_id, json.dumps(job_data))

        for i, url in enumerate(final_urls_to_scrape):
            # ... (rest of the scraping loop)
            log_terminal(f"--- [SCRAPER] Scraping URL {i+1}/{len(final_urls_to_scrape)}: {url} ---")
            
            page_scrape, context_scrape = None, None
            for attempt in range(2):
                try:
                    context_scrape = browser_instance.new_context(user_agent=random.choice(USER_AGENTS_LIST))
                    page_scrape = context_scrape.new_page()
                    page_scrape.goto(url, wait_until='domcontentloaded', timeout=45000)
                    
                    scraped_row = {"source_url": url}
                    for rule in element_rules:
                        field_name = rule.get("name")
                        selector = rule.get("selector")
                        try:
                            element_text = page_scrape.locator(selector).first.inner_text()
                            scraped_row[field_name] = element_text.strip() if element_text else None
                        except Exception as el_error:
                            log_terminal(f"--- [SCRAPER] Selector failed for '{field_name}': {el_error}")
                            scraped_row[field_name] = None
                    
                    scraped_row["scraped_at"] = datetime.now(timezone.utc).isoformat()
                    all_scraped_data.append(scraped_row)
                    log_terminal(f"--- [SCRAPER] Successfully processed {url} ---")
                    break 
                except Exception as e:
                    log_terminal(f"--- [SCRAPER] Attempt {attempt + 1} failed for {url}. Error: {e}")
                finally:
                    if page_scrape and not page_scrape.is_closed(): page_scrape.close()
                    if context_scrape: context_scrape.close()

            job_data["processed_urls"] = i + 1
            job_data["results"] = all_scraped_data
            redis_client.set(job_id, json.dumps(job_data))

        job_data["status"] = "complete"
        log_terminal(f"🎉 Scrape job '{job_id}' complete. Extracted {len(all_scraped_data)} items.")

    except Exception as e:
        log_terminal(f"❌ Scraper job '{job_id}' failed with a critical error: {e}")
        job_data["status"] = "failed"
        job_data["error"] = str(e)
    finally:
        redis_client.set(job_id, json.dumps(job_data))
        if page and not page.is_closed(): page.close()
        if context: context.close()
        log_terminal(f"--- [SCRAPER WORKER] Finished job: {job_id} ---")
