import uuid
import json
import base64
import requests
import os
import time
import traceback
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone, date, timedelta
from fastapi import FastAPI, UploadFile, File, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse
from shared_state import redis_client, log_terminal, log_action
from tasks import generate_preview_task, run_project_task, regenerate_content_task, regenerate_image_task, PROCESSED_URLS_KEY
from data_tasks import update_product_database_task
from openai import OpenAI
from phone_tasks import run_phone_scraper_task
from playwright.async_api import async_playwright
from urllib.parse import urljoin
import csv
from io import StringIO
from google_client import get_gsc_service
from google_auth_oauthlib.flow import Flow



app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Pydantic Models ---
class StagedProduct(BaseModel):
    class Config:
        extra = "ignore"
    
    status: str
    slug: str
    parsed_name: str
    original_url: str
    affiliate_link: str
    new_sale_price: Optional[float] = None
    new_regular_price: Optional[float] = None
    button_text: Optional[str] = None
    current_price: Any
    nearest_match: Optional[str] = None
    shopee_id: Optional[str] = None
    lazada_id: Optional[str] = None
    shop_id: Optional[str] = None
    action: Optional[str] = None        # To accept 'approve', 'link', 'ignore'
    linked_db_id: Optional[int] = None  # To accept the WC ID you linked
    matched_db_id: Optional[int] = None
    matched_db_slug: Optional[str] = None

class ProcessStagedPayload(BaseModel):
    job_id: str
    approved_products: List[StagedProduct]

class WordPressInspectPayload(BaseModel):
    url: str
    username: str
    password: str

class JobCreationResponse(BaseModel):
    job_id: str

class DiscoveredArticle(BaseModel):
    source_url: str
    title: str

class ManualDraftPayload(BaseModel):
    topic: str
    keywords: str
    notes: str
    prompt: str

class DashboardStats(BaseModel):
    total_posts: int
    draft_posts: int
    published_posts: int
    scheduled_posts: int
    fsc: str
    indexed: str
    not_indexed: str

class RunOptions(BaseModel):
    target_date: Optional[str] = None
    limit: Optional[int] = None
    custom_url_list: Optional[List[str]] = None

class ScrapeElementRule(BaseModel):
    name: str
    selector: str
    value: Optional[str] = None

class CrawlLevel(BaseModel):
    name: str
    selector: str

class ScrapeConfig(BaseModel):
    scrape_type: Optional[str] = None #<-- Make optional
    initial_urls: List[str]
    link_selector: Optional[str] = None
    crawling_levels: Optional[List[CrawlLevel]] = None
    final_urls: Optional[List[str]] = None
    element_rules: Optional[List[ScrapeElementRule]] = [] #<-- Make optional and default to empty list
    modelUrls: Optional[List[str]] = None

class Project(BaseModel):
    project_id: str = Field(default_factory=lambda: f"proj_{uuid.uuid4().hex[:10]}")
    project_name: str
    project_type: str
    scrape_config: ScrapeConfig
    llm_prompt_template: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_run_at: Optional[str] = None

class Draft(BaseModel):
    draft_id: str
    draft_type: str = 'wordpress_post'
    status: str
    source_url: str
    generated_at: str
    original_content: dict
    llm_prompt_template: str
    content_history: List[Dict[str, Any]] = []
    image_history: List[Dict[str, Any]] = []
    wordpress_post_id: Optional[int] = None
    featured_image_b64: Optional[str] = None
    focus_keyphrase: str
    seo_title: str
    meta_description: str
    slug: str
    post_category: str
    post_tags: List[str]
    post_title: str
    post_excerpt: str
    featured_image_prompt: str
    image_alt_text: str
    image_title: str
    post_content_html: str

class RegeneratePayload(BaseModel):
    edited_prompt: str

class SiteSelectionPayload(BaseModel):
    site_url: str

# --- Authentication ---
# This is the same redirect URI we configured in the Google Cloud Console.
REDIRECT_URI = "http://localhost:8000/api/auth/callback"
# This defines the permission we are asking for.
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly", "https://www.googleapis.com/auth/spreadsheets.readonly"]
# SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

@app.get("/api/auth/google")
async def auth_google():
    """
    Redirects the user to Google's OAuth consent screen.
    """
    flow = Flow.from_client_secrets_file(
        'client_secret.json', # We will create this file next
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    # In a real app, you would store the 'state' in the user's session
    # For now, we will log it for debugging.
    log_terminal(f"OAuth state created: {state}")
    return RedirectResponse(authorization_url)

@app.get("/api/auth/callback")
async def auth_callback(code: str, state: str):
    """
    Handles the callback from Google, fetches credentials, and securely stores them.
    """
    log_terminal(f"--- HIT: GET /api/auth/callback ---")
    log_terminal(f"Received OAuth code: {code}")
    
    flow = Flow.from_client_secrets_file(
        'client_secret.json',
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    
    try:
        # Exchange the authorization code for a credentials token
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Convert the credentials to a dictionary format for storing in Redis
        creds_dict = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        # --- THE FIX: Securely store the credentials in Redis ---
        # We'll save them as a JSON string under a single, well-known key.
        redis_client.set("gsc_credentials", json.dumps(creds_dict))
        log_terminal(f"✅ Successfully fetched and stored GSC credentials in Redis.")
        
        # Redirect the user back to the frontend root so the app can handle routing
        return RedirectResponse("http://localhost:5173/?status=success")

    except Exception as e:
        log_terminal(f"❌ Failed to fetch or store GSC token: {e}")
        # Redirect back to the frontend with an error status
        return RedirectResponse("http://localhost:5173/?status=error")

# --- WordPress Helper Functions ---
def publish_to_woocommerce(draft_data: dict, wp_url: str, auth_tuple: tuple, media_id: int):
    log_terminal(f"📦 Publishing draft {draft_data['draft_id']} to WooCommerce...")
    # This would be similar to the WordPress publishing logic but would:
    # 1. Post to the /wp-json/wp/v2/products endpoint
    # 2. Set 'post_type': 'product'
    # 3. Add WooCommerce-specific metadata like _price, _sku, and product attributes for specs
    log_terminal("✅ Mock Published to WooCommerce.")
    return {"link": f"{wp_url}/mock-product/{draft_data['slug']}", "id": 12345} # Return mock ID

def get_or_create_term(name: str, term_type: str, base_url: str, auth_tuple: tuple) -> Optional[int]:
    if not name:
        return None
    headers = {'User-Agent': 'Mozilla/5.0'}
    search_url = f"{base_url}/wp-json/wp/v2/{term_type}?search={name}"
    try:
        response = requests.get(search_url, headers=headers, auth=auth_tuple, timeout=10)
        response.raise_for_status()
        terms = response.json()
        for term in terms:
            if term['name'].lower() == name.lower():
                log_terminal(f"✅ Found existing {term_type[:-1]} '{name}' with ID {term['id']}.")
                return term['id']
        log_terminal(f"ℹ️ No {term_type[:-1]} named '{name}' found, creating it...")
        create_url = f"{base_url}/wp-json/wp/v2/{term_type}"
        create_payload = {'name': name}
        response = requests.post(create_url, headers=headers, json=create_payload, auth=auth_tuple, timeout=10)
        response.raise_for_status()
        new_term = response.json()
        log_terminal(f"✅ Created new {term_type[:-1]} '{name}' with ID {new_term['id']}.")
        return new_term['id']
    except requests.RequestException as e:
        log_terminal(f"❌ Could not get or create {term_type[:-1]} '{name}': {e}")
        return None

# Endpoints starts here...
@app.post("/api/projects/{project_id}/discover-new-articles", response_model=List[DiscoveredArticle])
async def discover_new_articles(project_id: str):
    """
    Performs a lightweight discovery of new, unprocessed articles for a project.
    """
    log_terminal(f"--- HIT: POST /api/projects/{project_id}/discover-new-articles ---")
    
    project_json = redis_client.get(f"project:{project_id}")
    if not project_json:
        raise HTTPException(status_code=404, detail="Project not found.")
    
    project_data = json.loads(project_json)
    config = project_data.get('scrape_config', {})
    source_url = config.get('initial_urls', [None])[0]
    link_selector = config.get('link_selector')

    if not all([source_url, link_selector]):
        raise HTTPException(status_code=400, detail="Project is not configured for discovery.")

    discovered_articles = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page()
        try:
            log_terminal(f"    - Discovering articles from: {source_url}")
            await page.goto(source_url, wait_until='domcontentloaded', timeout=60000)
            
            parent_selector = " > ".join(link_selector.split(' > ')[:-1])
            await page.wait_for_selector(parent_selector, timeout=30000)
            
            links = await page.locator(link_selector).all()
            for link_locator in links:
                href = await link_locator.get_attribute('href')
                title = await link_locator.inner_text()

                # --- THE FIX: Ignore irrelevant internal links ---
                if href and title and href != '#':
                    full_url = urljoin(source_url, href)
                    if not redis_client.sismember(PROCESSED_URLS_KEY, full_url):
                        discovered_articles.append({"source_url": full_url, "title": title})
            
            log_terminal(f"    - Discovery complete. Found {len(discovered_articles)} new articles.")
            return discovered_articles
        except Exception as e:
            log_terminal(f"❌ DISCOVERY FAILED: {e}")
            raise HTTPException(status_code=500, detail="Failed to discover new articles.")
        finally:
            await browser.close()

@app.post("/api/drafts/manual", status_code=202)
async def create_manual_draft(payload: ManualDraftPayload):
    """
    Creates a new draft from manual user input.
    """
    log_terminal("--- HIT: POST /api/drafts/manual ---")
    try:
        job_id = f"manual_gen_{uuid.uuid4().hex[:10]}"
        job_status = { "job_id": job_id, "status": "starting" }
        redis_client.set(f"job:{job_id}", json.dumps(job_status), ex=3600)

        # Import the new task
        from tasks import create_manual_draft_task
        create_manual_draft_task.delay(job_id, payload.dict())
        
        log_terminal(f"✍️ Queued manual draft generation. Job ID: {job_id}")
        return {"job_id": job_id}
    except Exception as e:
        log_terminal(f"❌ ERROR in /api/drafts/manual: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue manual draft creation task.")

# --- Data Management Endpoint ---
@app.post("/api/data/refresh-products", status_code=202)
async def refresh_product_database():
    try:
        update_product_database_task.delay()
        message = "Accepted: Product database refresh task has been queued."
        log_terminal(f"✅ {message}")
        return {"message": message}
    except Exception as e:
        log_terminal(f"❌ Failed to queue product database refresh task: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue the refresh task.")

# --- Approval Queue Endpoints ---
@app.get("/api/drafts", response_model=List[Draft])
async def get_all_drafts():
    # This endpoint is now specifically for the Approval Queue (drafts only)
    draft_ids = redis_client.smembers("drafts_set")
    if not draft_ids:
        return []
    
    draft_keys = [f"draft:{did}" for did in draft_ids]
    pipelines = redis_client.mget(draft_keys)
    posts = [json.loads(p) for p in pipelines if p]
    return posts

@app.get("/api/drafts/{draft_id}", response_model=Draft)
async def get_draft(draft_id: str):
    draft_json = redis_client.get(f"draft:{draft_id}")
    if not draft_json: raise HTTPException(status_code=404, detail="Draft not found.")
    return json.loads(draft_json)

@app.put("/api/drafts/{draft_id}", response_model=Draft)
async def update_draft(draft_id: str, draft_data: Draft):
    if not redis_client.exists(f"draft:{draft_id}"): raise HTTPException(status_code=404, detail="Draft not found.")
    redis_client.set(f"draft:{draft_id}", draft_data.model_dump_json())
    log_terminal(f"💾 Post '{draft_data.post_title}' (ID: {draft_id}) was updated locally.")
    return draft_data

@app.post("/api/drafts/{draft_id}/regenerate", status_code=202)
async def regenerate_draft(draft_id: str, payload: RegeneratePayload):
    if not redis_client.exists(f"draft:{draft_id}"):
        raise HTTPException(status_code=404, detail="Draft not found.")
    
    # Create a job_id for status tracking
    job_id = f"regen_content_{uuid.uuid4().hex[:10]}"
    job_status = { "job_id": job_id, "status": "starting" }
    redis_client.set(f"job:{job_id}", json.dumps(job_status), ex=3600)

    # Pass the job_id and the new edited_prompt to the Celery task
    regenerate_content_task.delay(job_id, draft_id, payload.edited_prompt)
    
    log_terminal(f"🔄 Queued content regeneration for draft ID: {draft_id}. Job ID: {job_id}")
    return {"job_id": job_id}

@app.post("/api/drafts/{draft_id}/regenerate-image", status_code=202)
async def regenerate_draft_image(draft_id: str):
    if not redis_client.exists(f"draft:{draft_id}"):
        raise HTTPException(status_code=404, detail="Draft not found.")
    
    job_id = f"regen_img_{uuid.uuid4().hex[:10]}"
    job_status = { "job_id": job_id, "status": "starting" }
    redis_client.set(f"job:{job_id}", json.dumps(job_status), ex=3600)

    regenerate_image_task.delay(job_id, draft_id)
    log_terminal(f"🎨 Queued image regeneration task for draft ID: {draft_id}. Job ID: {job_id}")
    return {"job_id": job_id}

@app.post("/api/drafts/{draft_id}/publish")
async def publish_draft(draft_id: str):
    draft_json = redis_client.get(f"draft:{draft_id}")
    if not draft_json: raise HTTPException(status_code=404, detail="Draft not found.")
    draft_data = json.loads(draft_json)

    required_fields = [
        'post_title', 'slug', 'post_content_html', 'seo_title', 
        'meta_description', 'focus_keyphrase', 'featured_image_b64'
    ]
    missing_fields = [field for field in required_fields if not draft_data.get(field)]
    if missing_fields:
        message = f"Cannot publish. The following fields are missing or empty: {', '.join(missing_fields)}"
        log_terminal(f"❌ Publishing validation failed for draft {draft_id}: {message}")
        raise HTTPException(status_code=400, detail=message)

    WP_URL = os.getenv("WP_URL")
    WP_USER = os.getenv("WP_USERNAME")
    WP_PASSWORD = os.getenv("WP_APPLICATION_PASSWORD")

    if not all([WP_URL, WP_USER, WP_PASSWORD]):
        raise HTTPException(status_code=500, detail="WordPress credentials are not configured on the server.")

    auth_tuple = (WP_USER, WP_PASSWORD)
    
    time.sleep(1)

    try:
        image_b64 = draft_data.get("featured_image_b64")
        image_data = base64.b64decode(image_b64)
        image_name = f"{draft_data['slug']}.png"
        
        log_terminal("⬆️ Uploading image to WordPress with metadata...")
        upload_url = f"{WP_URL.rstrip('/')}/wp-json/wp/v2/media"
        
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Content-Disposition': f'attachment; filename="{image_name}"',
        }

        media_id = None
        try:
            files = {'file': (image_name, image_data, 'image/png')}
            media_payload = {
                'title': draft_data.get('image_title'),
                'alt_text': draft_data.get('image_alt_text'),
                'status': 'publish'
            }
            upload_response = requests.post(
                upload_url, 
                headers=headers, 
                files=files,
                data=media_payload,
                auth=auth_tuple, 
                timeout=60
            )
            upload_response.raise_for_status()
            media_data = upload_response.json()
            media_id = media_data['id']
            log_terminal(f"✅ Image uploaded. Media ID: {media_id}")

        except requests.exceptions.RequestException as e:
            log_terminal("--- ❌ IMAGE UPLOAD FAILED: Detailed Server Response ---")
            if e.response is not None:
                log_terminal(f"    - Status Code: {e.response.status_code}")
                log_terminal(f"    - Headers: {e.response.headers}")
                log_terminal(f"    - Body: {e.response.text}")
            log_terminal("---------------------------------------------------------")
            raise

        draft_type = draft_data.get('draft_type', 'wordpress_post')
        
        if draft_type == 'woocommerce_product':
            response_data = publish_to_woocommerce(draft_data, WP_URL, auth_tuple, media_id)
        else:
            category_id = get_or_create_term(draft_data.get('post_category'), 'categories', WP_URL, auth_tuple)
            tag_ids = [tid for tid in [get_or_create_term(tag, 'tags', WP_URL, auth_tuple) for tag in draft_data.get('post_tags', [])] if tid is not None]

            post_payload = {
                'title': draft_data['post_title'],
                'content': draft_data['post_content_html'],
                'excerpt': draft_data.get('post_excerpt'),
                'status': 'publish',
                'slug': draft_data['slug'],
                'featured_media': media_id,
                'categories': [category_id] if category_id else [],
                'tags': tag_ids,
                'meta': {
                    '_yoast_wpseo_title': draft_data.get('seo_title'),
                    '_yoast_wpseo_focuskw': draft_data.get('focus_keyphrase'),
                    '_yoast_wpseo_metadesc': draft_data.get('meta_description'),
                    'source_url': draft_data.get('source_url')
                }
            }
            existing_post_id = draft_data.get('wordpress_post_id')
            post_headers = {'User-Agent': 'Mozilla/5.0'}
            if existing_post_id:
                log_terminal(f"📝 Updating existing post (ID: {existing_post_id}) in WordPress...")
                post_url = f"{WP_URL.rstrip('/')}/wp-json/wp/v2/posts/{existing_post_id}"
                post_response = requests.post(post_url, headers=post_headers, json=post_payload, auth=auth_tuple, timeout=30)
            else:
                log_terminal("📝 Creating new post in WordPress...")
                post_url = f"{WP_URL.rstrip('/')}/wp-json/wp/v2/posts"
                post_response = requests.post(post_url, headers=post_headers, json=post_payload, auth=auth_tuple, timeout=30)
            
            post_response.raise_for_status()
            response_data = post_response.json()
        
        log_terminal(f"✅ Post published successfully! URL: {response_data['link']}")

        draft_data['status'] = 'published'
        draft_data['wordpress_post_id'] = response_data.get('id')
        redis_client.set(f"draft:{draft_id}", json.dumps(draft_data))
        redis_client.srem("drafts_set", draft_id)
        redis_client.sadd("published_set", draft_id)

        return {"message": "Draft published successfully!", "url": response_data['link']}

    except requests.exceptions.RequestException as e:
        error_detail = f"An error occurred during publishing: {e.response.text if e.response else e}"
        log_terminal(f"❌ Publishing failed: {error_detail}")
        raise HTTPException(status_code=500, detail=error_detail)

# --- Other Endpoints ---
@app.post("/api/request-page-preview/")
async def request_page_preview(payload: dict):
    url = payload.get("url")
    project_type = payload.get("project_type", "standard_article")
    if not url: raise HTTPException(status_code=400, detail="URL is required.")
    
    job_id = f"preview_{uuid.uuid4().hex[:10]}"
    generate_preview_task.delay(job_id, url, project_type)
    return {"job_id": job_id}

@app.get("/api/get-preview-result/{job_id}")
async def get_preview_result(job_id: str):
    result_json = redis_client.get(job_id)
    if not result_json: return {"status": "pending"}
    return json.loads(result_json)

@app.post("/api/projects", status_code=201)
async def save_project(project_data: Project):
    project_id = project_data.project_id
    redis_client.set(f"project:{project_id}", project_data.model_dump_json())
    redis_client.sadd("projects_set", project_id)
    log_terminal(f"✅ Project '{project_data.project_name}' (ID: {project_id}) was saved.")
    return {"message": "Project saved successfully", "project_id": project_id}

@app.get("/api/projects", response_model=List[Project])
async def get_all_projects():
    project_ids = redis_client.smembers("projects_set")
    if not project_ids: return []
    project_pipelines = redis_client.mget([f"project:{pid}" for pid in project_ids])
    projects = [json.loads(p) for p in project_pipelines if p]
    return projects

@app.post("/api/projects/{project_id}/run")
async def run_project(project_id: str, options: RunOptions):
    project_json = redis_client.get(f"project:{project_id}")
    if not project_json: raise HTTPException(status_code=404, detail="Project not found.")
    project_data = json.loads(project_json)
    job_id = f"run_{uuid.uuid4().hex[:10]}"
    
    project_type = project_data.get("project_type")
    
    # --- THIS IS THE FINAL, CORRECTED ROUTING LOGIC ---
    if project_type == "brightdata_mcp":
        from tasks import run_mcp_scrape_task
        run_mcp_scrape_task.delay(job_id, project_data)
        log_terminal(f"📊 Kicked off BRIGHT DATA MCP run for project '{project_data.get('project_name')}'. Job ID: {job_id}")
    
    elif project_type == "phone_spec_scraper":
        run_phone_scraper_task.delay(job_id, project_data)
        log_terminal(f"🚀 Kicked off PHONE SCRAPER run for project '{project_data.get('project_name')}'. Job ID: {job_id}")

    else: # Default is the standard article scraper
        run_project_task.delay(
            job_id,
            project_data,
            target_date=options.target_date,
            limit=options.limit,
            custom_url_list=options.custom_url_list
        )
        log_terminal(f"🚀 Kicked off standard run for project '{project_data.get('project_name')}'. Job ID: {job_id}")

    job_status = {
        "job_id": job_id, "project_id": project_id,
        "project_name": project_data.get("project_name"),
        "status": "starting", "total_urls": 0, "processed_urls": 0,
        "results": [], "started_at": datetime.now(timezone.utc).isoformat()
    }
    redis_client.set(f"job:{job_id}", json.dumps(job_status))
    
    return {"message": "Project run started successfully.", "job_id": job_id}

@app.get("/api/jobs/status/{job_id}")
async def get_run_status(job_id: str):
    job_json = redis_client.get(f"job:{job_id}")
    if not job_json:
        job_json = redis_client.get(job_id)
        if not job_json: raise HTTPException(status_code=404, detail="Job not found.")
    return json.loads(job_json)

# new endpoints
@app.get("/api/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats():
    """
    Provides aggregated statistics for the main dashboard.
    """
    log_terminal("--- HIT: GET /api/dashboard/stats ---") # <-- NEW LOG
    try:
        draft_count = redis_client.scard("drafts_set")
        published_count = redis_client.scard("published_set")
        
        stats = {
            "draft_posts": draft_count,
            "published_posts": published_count,
            "total_posts": draft_count + published_count,
            "scheduled_posts": 0,
            "fsc": "N/A",
            "indexed": "N/A",
            "not_indexed": "N/A"
        }
        return stats
    except Exception as e:
        log_terminal(f"❌ ERROR in /api/dashboard/stats: {e}") # <-- Enhanced Error Log
        raise HTTPException(status_code=500, detail="Failed to retrieve dashboard stats.")

# --- NEW: Google Search Console Integration ---
@app.get("/api/gsc/sites")
async def get_gsc_sites():
    """
    Fetches a list of websites verified in the user's GSC account.
    """
    log_terminal("--- HIT: GET /api/gsc/sites ---")
    service = get_gsc_service()
    if not service:
        raise HTTPException(status_code=401, detail="User is not authenticated with Google.")
    
    try:
        site_list = service.sites().list().execute()
        return site_list.get('siteEntry', [])
    except Exception as e:
        log_terminal(f"❌ Failed to fetch GSC sites: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch sites from Google Search Console.")

# --- NEW: Database Management ---
@app.post("/api/database/backup", status_code=202)
async def create_database_backup():
    """
    Triggers a background save of the Redis database to its dump file.
    """
    log_terminal("--- HIT: POST /api/database/backup ---")
    try:
        redis_client.bgsave()
        log_action("MANUAL_BACKUP_CREATED")
        return {"message": "Database backup process started in the background. It may take a moment to complete."}
    except Exception as e:
        log_terminal(f"❌ ERROR triggering database backup: {e}")
        raise HTTPException(status_code=500, detail="Failed to start database backup.")

@app.get("/api/database/backup/download")
async def download_database_backup():
    """
    Allows the user to download the latest Redis backup file.
    """
    log_terminal("--- HIT: GET /api/database/backup/download ---")
    # This path is determined by the 'volumes' section in your docker-compose.yml
    # It points to the location of the redis-data volume on the host machine.
    # This is a common default path for Docker on Linux.
    backup_file_path = "/var/lib/docker/volumes/contentpipeline_redis-data/_data/dump.rdb"
    
    if not os.path.exists(backup_file_path):
        log_terminal(f"❌ Backup file not found at {backup_file_path}")
        raise HTTPException(status_code=404, detail="Backup file not found. Please generate a backup first.")
    
    return FileResponse(path=backup_file_path, filename="redis_backup.rdb", media_type='application/octet-stream')

@app.get("/api/posts/{post_id}/seo-stats")
async def get_post_seo_stats(post_id: str):
    """
    Fetches basic SEO stats (clicks, impressions) for a single post.
    NOTE: This is a placeholder for our future daily caching task.
    For now, it performs a live API call for demonstration.
    """
    log_terminal(f"--- HIT: GET /api/posts/{post_id}/seo-stats ---")
    service = get_gsc_service()
    if not service:
        raise HTTPException(status_code=401, detail="User is not authenticated with Google.")

    post_key = f"draft:{post_id}"
    post_json = redis_client.get(post_key)
    if not post_json:
        raise HTTPException(status_code=404, detail="Post not found.")
    
    post_data = json.loads(post_json)
    post_url = post_data.get("source_url") # Assuming source_url is the published URL for now
    
    # We need to know which GSC site to query. For now, we'll hardcode it.
    # In the future, this will come from a user setting.
    # IMPORTANT: Replace 'https://www.gadgetph.com/' with the URL you have in GSC.
    site_url = "https://www.gadgetph.com/" 

    try:
        request = {
            'startDate': '2025-01-01', # A wide date range for now
            'endDate': '2025-12-31',
            'dimensions': ['page'],
            'dimensionFilterGroups': [{
                'filters': [{
                    'dimension': 'page',
                    'operator': 'equals',
                    'expression': post_url
                }]
            }]
        }
        response = service.searchanalytics().query(siteUrl=site_url, body=request).execute()
        
        # Process the response
        rows = response.get('rows', [])
        if not rows:
            return {"clicks": 0, "impressions": 0}
        
        return {
            "clicks": rows[0]['clicks'],
            "impressions": rows[0]['impressions']
        }

    except Exception as e:
        log_terminal(f"❌ Failed to fetch SEO stats for {post_url}: {e}")
        return {"clicks": "N/A", "impressions": "N/A"}

@app.get("/api/dashboard/seo-performance-graph")
async def get_seo_performance_graph_data():
    """
    Aggregates the last 30 days of GSC data for the dashboard chart.
    """
    log_terminal("--- HIT: GET /api/dashboard/seo-performance-graph ---")
    
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    published_ids = redis_client.smembers("published_set")
    if not published_ids:
        return []

    aggregated_data = {}
    current_date = start_date
    while current_date < end_date:
        day_str = current_date.strftime('%Y-%m-%d')
        daily_total_clicks = 0
        daily_total_impressions = 0
        
        for post_id in published_ids:
            cache_key = f"gsc:metrics:{post_id}:{day_str}"
            cached_metric = redis_client.get(cache_key)
            if cached_metric:
                metric_data = json.loads(cached_metric)
                daily_total_clicks += metric_data.get('clicks', 0)
                daily_total_impressions += metric_data.get('impressions', 0)
        
        aggregated_data[day_str] = {
            "clicks": daily_total_clicks,
            "impressions": daily_total_impressions
        }
        current_date += timedelta(days=1)
        
    chart_data = [{"date": day, "clicks": data["clicks"], "impressions": data["impressions"]} for day, data in aggregated_data.items()]
    
    return chart_data

@app.post("/api/gsc/fetch-now", status_code=202)
async def trigger_gsc_fetch():
    """
    Manually triggers the GSC data fetching background task.
    """
    log_terminal("--- HIT: POST /api/gsc/fetch-now ---")
    try:
        # Import the task and queue it immediately
        from tasks import fetch_gsc_data_task
        fetch_gsc_data_task.delay()
        return {"message": "GSC data fetch task has been successfully queued."}
    except Exception as e:
        log_terminal(f"❌ ERROR triggering GSC fetch task: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue the GSC data fetch task.")

@app.get("/api/posts", response_model=List[Draft])
async def get_all_posts():
    """
    Fetches all posts, both drafts and published, for the Content Library.
    """
    log_terminal("--- HIT: GET /api/posts ---") # <-- NEW LOG
    try:
        draft_ids = redis_client.smembers("drafts_set")
        published_ids = redis_client.smembers("published_set")
        all_ids = draft_ids.union(published_ids)
        if not all_ids:
            return []
        
        post_keys = [f"draft:{pid}" for pid in all_ids]
        posts_json = redis_client.mget(post_keys)
        
        all_posts = [json.loads(p) for p in posts_json if p]
        return all_posts
    except Exception as e:
        log_terminal(f"❌ ERROR in /api/posts: {e}") # <-- Enhanced Error Log
        raise HTTPException(status_code=500, detail="Failed to retrieve posts.")

@app.delete("/api/posts/{post_id}", status_code=204)
async def delete_post(post_id: str):
    """
    Deletes a specific post and logs the action in a single atomic transaction.
    """
    log_terminal(f"--- HIT: DELETE /api/posts/{post_id} ---")
    post_key = f"draft:{post_id}"

    try:
        # 1. Verify the post exists before doing anything
        post_data_json = redis_client.get(post_key)
        if not post_data_json:
            log_terminal(f"⚠️  Delete failed: Post with ID {post_id} not found.")
            raise HTTPException(status_code=404, detail="Post not found.")
        
        post_data = json.loads(post_data_json)
        post_title = post_data.get("post_title", "Unknown Title")
        log_terminal(f"Found post '{post_title}'. Preparing to delete.")

        # 2. Create the log entry BEFORE the pipeline
        log_entry = {
            "action": "POST_DELETED",
            "details": {"post_id": post_id, "title": post_title},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # 3. Use a pipeline to perform all deletions AND logging atomically
        pipe = redis_client.pipeline()
        
        # --- Deletion commands ---
        pipe.srem("drafts_set", post_id)
        pipe.srem("published_set", post_id)
        pipe.delete(post_key)
        
        # --- Logging commands ---
        pipe.lpush("action_history", json.dumps(log_entry))
        pipe.ltrim("action_history", 0, 999)
        
        # 4. Execute all commands in one go
        pipe.execute()
        
        log_terminal(f"🗑️ Post '{post_title}' (ID: {post_id}) was successfully deleted and logged.")
        
        return

    except Exception as e:
        log_terminal(f"❌ UNEXPECTED ERROR in /api/posts/{post_id}: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred during post deletion.")

@app.get("/api/account/history")
async def get_action_history():
    """
    Retrieves the last 100 actions from the history log.
    """
    log_terminal("--- HIT: GET /api/account/history ---") # <-- NEW LOG
    try:
        history_json = redis_client.lrange("action_history", 0, 99)
        history = [json.loads(item) for item in history_json]
        return history
    except Exception as e:
        log_terminal(f"❌ ERROR in /api/account/history: {e}") # <-- Enhanced Error Log
        raise HTTPException(status_code=500, detail="Failed to retrieve action history.")
    
@app.get("/api/published-posts", response_model=List[Draft])
async def get_published_posts():
    """
    Fetches only published posts.
    """
    log_terminal("--- HIT: GET /api/published-posts ---")
    try:
        published_ids = redis_client.smembers("published_set")
        if not published_ids:
            return []
        
        post_keys = [f"draft:{pid}" for pid in published_ids]
        posts_json = redis_client.mget(post_keys)
        
        published_posts = [json.loads(p) for p in posts_json if p]
        return published_posts
    except Exception as e:
        log_terminal(f"❌ ERROR in /api/published-posts: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve published posts.")
    
@app.delete("/api/projects/{project_id}", status_code=204)
async def delete_project(project_id: str):
    """
    Deletes a specific project configuration and logs the action atomically.
    """
    log_terminal(f"--- HIT: DELETE /api/projects/{project_id} ---")
    project_key = f"project:{project_id}"

    try:
        project_data_json = redis_client.get(project_key)
        if not project_data_json:
            raise HTTPException(status_code=404, detail="Project not found.")
        
        project_data = json.loads(project_data_json)
        project_name = project_data.get("project_name", "Unknown Project")

        # --- THE FIX: Create the log entry BEFORE the pipeline ---
        log_entry = {
            "action": "PROJECT_DELETED",
            "details": {"project_id": project_id, "name": project_name},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Use a pipeline for atomic deletion AND logging
        pipe = redis_client.pipeline()
        pipe.srem("projects_set", project_id)
        pipe.delete(project_key)
        
        # --- ADD logging commands to the same pipeline ---
        pipe.lpush("action_history", json.dumps(log_entry))
        pipe.ltrim("action_history", 0, 999)
        
        # Execute all commands in one go
        pipe.execute()
        
        log_terminal(f"🗑️ Project '{project_name}' (ID: {project_id}) was deleted and logged.")
        
        return

    except Exception as e:
        log_terminal(f"❌ ERROR in /api/projects/{project_id}: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred during project deletion.")
    
@app.post("/api/gsc/active-site")
async def set_active_gsc_site(payload: SiteSelectionPayload):
    """
    Saves the user's selected GSC site URL to Redis.
    """
    log_terminal(f"--- HIT: POST /api/gsc/active-site ---")
    try:
        redis_client.set("gsc_active_site", payload.site_url)
        log_action("GSC_SITE_SELECTED", {"site_url": payload.site_url})
        log_terminal(f"✅ Active GSC site set to: {payload.site_url}")
        return {"message": "Active site updated successfully."}
    except Exception as e:
        log_terminal(f"❌ ERROR setting active GSC site: {e}")
        raise HTTPException(status_code=500, detail="Failed to save active site selection.")

@app.get("/api/gsc/active-site")
async def get_active_gsc_site():
    """
    Retrieves the currently selected active GSC site URL from Redis.
    """
    log_terminal("--- HIT: GET /api/gsc/active-site ---")
    try:
        active_site = redis_client.get("gsc_active_site")
        if not active_site:
            # Return a default empty response if no site has been selected yet
            return {"site_url": None}
        return {"site_url": active_site}
    except Exception as e:
        log_terminal(f"❌ ERROR getting active GSC site: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve active site selection.")
    
@app.post("/api/sync/wordpress", status_code=202)
async def trigger_wordpress_sync():
    """
    Manually triggers the WordPress post synchronization task.
    """
    log_terminal("--- HIT: POST /api/sync/wordpress ---")
    try:
        from tasks import full_wordpress_sync_task
        full_wordpress_sync_task.delay()
        return {"message": "WordPress synchronization task has been successfully queued."}
    except Exception as e:
        log_terminal(f"❌ ERROR triggering WordPress sync task: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue the WordPress sync task.")
    
@app.get("/api/gsc/performance")
async def get_gsc_performance_data(start_date_str: str, end_date_str: str):
    """
    Aggregates GSC data for a specified date range.
    Dates should be in YYYY-MM-DD format.
    """
    log_terminal(f"--- HIT: GET /api/gsc/performance (Range: {start_date_str} to {end_date_str}) ---")
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Please use YYYY-MM-DD.")

    published_ids = redis_client.smembers("published_set")
    if not published_ids:
        return {"summary": {"total_clicks": 0, "total_impressions": 0}, "daily_data": []}

    # Aggregate data for the date range
    aggregated_data = {}
    total_clicks = 0
    total_impressions = 0
    
    current_date = start_date
    while current_date <= end_date:
        day_str = current_date.strftime('%Y-%m-%d')
        daily_total_clicks = 0
        daily_total_impressions = 0
        
        for post_id in published_ids:
            cache_key = f"gsc:metrics:{post_id}:{day_str}"
            cached_metric = redis_client.get(cache_key)
            if cached_metric:
                metric_data = json.loads(cached_metric)
                daily_total_clicks += metric_data.get('clicks', 0)
                daily_total_impressions += metric_data.get('impressions', 0)
        
        aggregated_data[day_str] = {
            "clicks": daily_total_clicks,
            "impressions": daily_total_impressions
        }
        total_clicks += daily_total_clicks
        total_impressions += daily_total_impressions
        
        current_date += timedelta(days=1)
        
    # Format data for the chart and summary
    chart_data = [{"date": day, "clicks": data["clicks"], "impressions": data["impressions"]} for day, data in aggregated_data.items()]
    summary_data = {"total_clicks": total_clicks, "total_impressions": total_impressions}
    
    return {"summary": summary_data, "daily_data": chart_data}

@app.get("/api/posts/with-stats")
async def get_all_posts_with_stats():
    """
    Fetches all posts and enriches published ones with the latest GSC stats.
    """
    log_terminal("--- HIT: GET /api/posts/with-stats ---")
    try:
        draft_ids = redis_client.smembers("drafts_set")
        published_ids = redis_client.smembers("published_set")
        all_ids = draft_ids.union(published_ids)
        if not all_ids:
            return []
        
        post_keys = [f"draft:{pid}" for pid in all_ids]
        posts_json = redis_client.mget(post_keys)
        
        all_posts = []
        yesterday_str = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')

        for post_json in posts_json:
            if not post_json: continue
            
            post = json.loads(post_json)
            # If the post is published, try to find its stats
            if post.get("status") == "published":
                cache_key = f"gsc:metrics:{post['draft_id']}:{yesterday_str}"
                cached_metric = redis_client.get(cache_key)
                if cached_metric:
                    metric_data = json.loads(cached_metric)
                    post['clicks'] = metric_data.get('clicks', 0)
                    post['impressions'] = metric_data.get('impressions', 0)
                else:
                    post['clicks'] = 0
                    post['impressions'] = 0
            all_posts.append(post)
            
        return all_posts
    except Exception as e:
        log_terminal(f"❌ Could not retrieve posts with stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve posts with stats.")

@app.get("/api/gsc/insights")
async def get_gsc_insights():
    """
    Retrieves the latest cached GSC insights data.
    """
    log_terminal("--- HIT: GET /api/gsc/insights ---")
    try:
        insights_json = redis_client.get("gsc_insights_cache")
        if not insights_json:
            # Return an empty structure if no insights have been cached yet
            return {
                "top_content": [],
                "top_queries": [],
                "top_countries": [],
                "last_updated": None
            }
        
        insights_data = json.loads(insights_json)
        return insights_data
    except Exception as e:
        log_terminal(f"❌ ERROR getting GSC insights: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve GSC insights data.")
    
@app.post("/api/gsc/fetch-insights-now", status_code=202)
async def trigger_gsc_insights_fetch():
    """
    Manually triggers the GSC insights fetching background task.
    """
    log_terminal("--- HIT: POST /api/gsc/fetch-insights-now ---")
    try:
        from tasks import fetch_gsc_insights_task
        fetch_gsc_insights_task.delay()
        return {"message": "GSC insights fetch task has been successfully queued."}
    except Exception as e:
        log_terminal(f"❌ ERROR triggering GSC insights task: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue the GSC insights fetch task.")

# --- NEW: Tools Endpoints ---
@app.post("/api/tools/inspect-wordpress", response_model=JobCreationResponse)
async def inspect_wordpress_site(payload: WordPressInspectPayload):
    """
    Kicks off a background task to inspect a WordPress site's structure.
    """
    log_terminal("--- HIT: POST /api/tools/inspect-wordpress ---")
    try:
        from tasks import inspect_wordpress_task
        
        job_id = f"inspect_{uuid.uuid4().hex[:10]}"
        job_status = {
            "job_id": job_id,
            "status": "starting",
            "progress": 0,
            "result_key": f"inspection_result:{job_id}" # Key for storing the result
        }
        redis_client.set(f"job:{job_id}", json.dumps(job_status), ex=3600)

        inspect_wordpress_task.delay(job_id, payload.dict())
        
        log_terminal(f"✅ Queued WordPress inspection for {payload.url}. Job ID: {job_id}")
        return {"job_id": job_id}
    except Exception as e:
        log_terminal(f"❌ ERROR queuing WordPress inspection: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue the inspection task.")

@app.get("/api/tools/download-inspection-result/{job_id}")
async def download_inspection_result(job_id: str):
    """
    Converts the JSON result of an inspection to CSV and serves it for download.
    """
    log_terminal(f"--- HIT: GET /api/tools/download-inspection-result/{job_id} ---")
    result_key = f"inspection_result:{job_id}"
    result_json = redis_client.get(result_key)

    if not result_json:
        raise HTTPException(status_code=404, detail="Inspection result not found or expired.")

    data = json.loads(result_json)
    if not data:
        raise HTTPException(status_code=404, detail="Result data is empty.")
    
    # --- THE FIX: Explicitly handle headers and empty values ---
    
    # 1. Define a fixed set of headers to ensure consistency.
    fieldnames = ["Title", "URL", "Type", "Category"]
    
    # 2. Prepare the data, replacing any missing or empty values with "N/A".
    cleaned_data = []
    for row in data:
        cleaned_row = {field: row.get(field) or "N/A" for field in fieldnames}
        cleaned_data.append(cleaned_row)
        
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(cleaned_data)
    
    csv_data = output.getvalue()
    
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=wordpress_inspection_{job_id}.csv"}
    )

@app.get("/api/products")
async def get_all_products():
    """
    Retrieves all product data from the local product_database.json file.
    """
    log_terminal("--- HIT: GET /api/products ---")
    try:
        # This assumes product_database.json is in the same directory as main.py
        with open("product_database.json", 'r', encoding='utf-8') as f:
            products = json.load(f)
        return products
    except FileNotFoundError:
        log_terminal("⚠️  product_database.json not found. Returning empty list.")
        return []
    except Exception as e:
        log_terminal(f"❌ ERROR reading product_database.json: {e}")
        raise HTTPException(status_code=500, detail="Failed to read product database.")

@app.post("/api/import/google-sheet", response_model=JobCreationResponse)
async def import_from_google_sheet(payload: dict):
    """
    Kicks off a background task to import and parse data from a Google Sheet.
    """
    log_terminal("--- HIT: POST /api/import/google-sheet ---")
    try:
        from tasks import import_from_google_sheet_task
        
        sheet_url = payload.get("sheet_url")
        if not sheet_url:
            raise HTTPException(status_code=400, detail="Google Sheet URL is required.")

        job_id = f"import_{uuid.uuid4().hex[:10]}"
        job_status = { "job_id": job_id, "status": "starting" }
        redis_client.set(f"job:{job_id}", json.dumps(job_status), ex=3600)

        import_from_google_sheet_task.delay(job_id, sheet_url)
        
        log_terminal(f"✅ Queued Google Sheet import for {sheet_url}. Job ID: {job_id}")
        return {"job_id": job_id}
    except Exception as e:
        log_terminal(f"❌ ERROR queuing Google Sheet import: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue the import task.")
    
@app.get("/api/import/staged-data/{job_id}", response_model=List[StagedProduct])
async def get_staged_data(job_id: str):
    """
    Retrieves the staged product data for a given import job for user review.
    """
    log_terminal(f"--- HIT: GET /api/import/staged-data/{job_id} ---")
    staging_key = f"staging_area:{job_id}"
    staged_json = redis_client.get(staging_key)

    if not staged_json:
        raise HTTPException(status_code=404, detail="Staged data not found or expired.")
    
    return json.loads(staged_json)

@app.post("/api/import/process-staged-data", response_model=JobCreationResponse)
async def process_staged_data(payload: ProcessStagedPayload):
    """
    (ROBUST LOGGING VERSION)
    Kicks off the background sync task, with detailed step-logging
    and full exception traceback reporting.
    """
    log_terminal("--- HIT: POST /api/import/process-staged-data ---")
    try:
        from data_tasks import update_woocommerce_products_task
        
        final_job_id = f"wcsync_{uuid.uuid4().hex[:10]}"
        job_status = { "job_id": final_job_id, "status": "starting" }
        log_terminal("    - Step 1: Setting job status in Redis...")
        redis_client.set(f"job:{final_job_id}", json.dumps(job_status), ex=3600)
        log_terminal("    - Step 1: SUCCESS.")

        # --- This is the part that is failing ---
        log_terminal("    - Step 2: Converting Pydantic models to dict list (using .dict())...")
        products_as_dict_list = [p.dict() for p in payload.approved_products]
        # products_as_dict_list = [p.model_dump() for p in payload.approved_products] # <-- This is the v2 command
        log_terminal(f"    - Step 2: SUCCESS. Converted {len(products_as_dict_list)} models.")

        log_terminal("    - Step 3: Calling .delay() to queue Celery task...")
        update_woocommerce_products_task.delay(final_job_id, products_as_dict_list)
        log_terminal("    - Step 3: SUCCESS. Task successfully queued.")
        # --- End of fail zone ---

        log_terminal(f"✅ Queued final WooCommerce sync. Job ID: {final_job_id}")
        return {"job_id": final_job_id}

    except Exception as e:
        # --- NEW: FULL TRACEBACK LOGGING ---
        error_details = traceback.format_exc()
        log_terminal("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        log_terminal("❌ FATAL ERROR IN process_staged_data ❌")
        log_terminal(f"Exception Type: {type(e)}")
        log_terminal(f"Exception Details: {e}")
        log_terminal(f"Full Traceback:\n{error_details}")
        log_terminal("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        
        # Also print to stdout directly just in case log_terminal has an issue
        print(f"--- ❌ FATAL ERROR: {error_details} ---", flush=True)

        raise HTTPException(status_code=500, detail="Failed to queue task. Check backend-1 log for full traceback.")

@app.get("/api/import/staged-data/{job_id}", response_model=List[StagedProduct])
async def get_staged_data(job_id: str):
    """
    Retrieves the staged product data for a given import job for user review.
    """
    log_terminal(f"--- HIT: GET /api/import/staged-data/{job_id} ---")
    staging_key = f"staging_area:{job_id}"
    staged_json = redis_client.get(staging_key)

    if not staged_json:
        raise HTTPException(status_code=404, detail="Staged data not found or expired.")
    
    return json.loads(staged_json)

@app.post("/api/import/process-staged-data", response_model=JobCreationResponse)
async def process_staged_data(payload: ProcessStagedPayload):
    """
    Kicks off a background task to update WooCommerce with the user's
    approved products from the staging area.
    """
    log_terminal("--- HIT: POST /api/import/process-staged-data ---")
    try:
        from data_tasks import update_woocommerce_products_task
        
        final_job_id = f"wcsync_{uuid.uuid4().hex[:10]}"
        job_status = { "job_id": final_job_id, "status": "starting" }
        redis_client.set(f"job:{final_job_id}", json.dumps(job_status), ex=3600)

        products_as_dict_list = [p.dict() for p in payload.approved_products]
        update_woocommerce_products_task.delay(final_job_id, products_as_dict_list)
        
        log_terminal(f"✅ Queued final WooCommerce sync. Job ID: {final_job_id}")
        return {"job_id": final_job_id}
    except Exception as e:
        log_terminal(f"❌ ERROR queuing final WooCommerce sync: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue the final sync task.")
    
@app.get("/api/run-migration")
async def run_migration():
    """
    A temporary, one-time endpoint to trigger the database migration task.
    """
    log_terminal("--- HIT: GET /api/run-migration ---")
    try:
        from tasks import migrate_product_database_task
        task = migrate_product_database_task.delay()
        return {"message": "Database migration task has been queued. Check the Celery worker logs for progress and result.", "task_id": task.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sync/run-master-sync", response_model=JobCreationResponse)
async def run_master_sync():
    """
    Manually triggers the full WordPress synchronization task.
    """
    log_terminal("--- HIT: POST /api/sync/run-master-sync ---")
    try:
        from tasks import full_wordpress_sync_task
        
        job_id = f"sync_{uuid.uuid4().hex[:10]}"
        job_status = { "job_id": job_id, "status": "starting" }
        redis_client.set(f"job:{job_id}", json.dumps(job_status), ex=3600)

        full_wordpress_sync_task.delay(job_id)
        
        return {"job_id": job_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to queue the sync task.")

@app.put("/api/import/staged-data/{job_id}")
async def save_staged_data(job_id: str, staged_products: List[StagedProduct]):
    """
    Saves the user's edits to the staged data back to Redis.
    """
    log_terminal(f"--- HIT: PUT /api/import/staged-data/{job_id} ---")
    try:
        staging_key = f"staging_area:{job_id}"
        redis_client.set(staging_key, json.dumps([p.dict() for p in staged_products]), ex=3600)
        log_action("STAGED_DATA_SAVED", {"job_id": job_id})
        return {"message": "Changes saved successfully."}
    except Exception as e:
        log_terminal(f"❌ ERROR saving staged data: {e}")
        raise HTTPException(status_code=500, detail="Failed to save changes.")

@app.get("/api/run-enrichment")
async def run_enrichment():
    """
    A temporary, one-time endpoint to trigger the database enrichment task.
    """
    log_terminal("--- HIT: GET /api/run-enrichment ---")
    try:
        from tasks import enrich_database_task
        task = enrich_database_task.delay()
        return {"message": "Database enrichment task has been queued. Check the Celery worker logs for progress and result.", "task_id": task.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/run-schema-upgrade")
async def run_schema_upgrade():
    """
    A temporary, one-time endpoint to trigger the database schema upgrade task.
    """
    log_terminal("--- HIT: GET /api/run-schema-upgrade ---")
    try:
        from tasks import upgrade_database_schema_task
        task = upgrade_database_schema_task.delay()
        return {"message": "Database schema upgrade task has been queued. Check the Celery worker logs for progress.", "task_id": task.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/tools/inspect-product/{product_id}")
async def get_live_product_data(product_id: int):
    """
    Kicks off a background task to fetch the full, raw JSON for a single
    product directly from WooCommerce for debugging.
    """
    log_terminal(f"--- HIT: GET /api/tools/inspect-product/{product_id} ---")
    try:
        from data_tasks import inspect_wc_product_task # Import our new task
        
        job_id = f"inspect_wc_{product_id}_{uuid.uuid4().hex[:6]}"
        job_status = { "job_id": job_id, "status": "starting" }
        redis_client.set(f"job:{job_id}", json.dumps(job_status), ex=3600)

        inspect_wc_product_task.delay(job_id, product_id)
        
        return {"job_id": job_id}
    except Exception as e:
        log_terminal(f"❌ ERROR queuing inspection task: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue the inspection task.")