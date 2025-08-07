import uuid
import json
import base64
import requests
import os
import time
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from shared_state import redis_client, log_terminal
from tasks import generate_preview_task, run_project_task, regenerate_content_task, regenerate_image_task
from data_tasks import update_product_database_task
from openai import OpenAI

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
class RunOptions(BaseModel):
    target_date: Optional[str] = None
    limit: Optional[int] = None

class ScrapeElementRule(BaseModel):
    name: str
    selector: str
    value: Optional[str] = None

class CrawlLevel(BaseModel):
    name: str
    selector: str

class ScrapeConfig(BaseModel):
    scrape_type: str
    initial_urls: List[str]
    crawling_levels: Optional[List[CrawlLevel]] = None
    final_urls: Optional[List[str]] = None
    element_rules: List[ScrapeElementRule]
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
    status: str
    source_url: str
    generated_at: str
    original_content: dict
    llm_prompt_template: str
    content_history: List[Dict[str, Any]] = []
    wordpress_post_id: Optional[int] = None
    featured_image_b64: Optional[str] = None
    focus_keyphrase: str
    seo_title: str
    meta_description: str
    slug: str
    post_category: str
    post_tags: List[str]
    post_title: str
    featured_image_prompt: str
    image_alt_text: str
    image_title: str
    post_content_html: str

# --- WordPress Helper Functions ---
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
    draft_ids = redis_client.smembers("drafts_set")
    published_ids = redis_client.smembers("published_set")
    all_ids = draft_ids.union(published_ids)
    if not all_ids: return []
    pipelines = redis_client.mget([f"draft:{did}" for did in all_ids])
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
async def regenerate_draft(draft_id: str):
    if not redis_client.exists(f"draft:{draft_id}"):
        raise HTTPException(status_code=404, detail="Draft not found.")
    regenerate_content_task.delay(draft_id)
    log_terminal(f"🔄 Queued regeneration task for draft ID: {draft_id}")
    return {"message": "Content regeneration has been queued."}

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
        # 1. Upload Image
        image_b64 = draft_data.get("featured_image_b64")
        image_data = base64.b64decode(image_b64)
        image_name = f"{draft_data['slug']}.png"
        
        log_terminal("⬆️ Uploading image to WordPress...")
        upload_url = f"{WP_URL}/wp-json/wp/v2/media"
        
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Content-Disposition': f'attachment; filename="{image_name}"',
            'Content-Type': 'image/png'
        }

        try:
            upload_response = requests.post(
                upload_url, 
                headers=headers, 
                data=image_data, 
                auth=auth_tuple, 
                timeout=60
            )
            upload_response.raise_for_status()
            media_data = upload_response.json()
            media_id = media_data['id']
            log_terminal(f"✅ Image uploaded. Media ID: {media_id}")

            # *** THE FIX: Update image metadata in a separate, standard request ***
            update_media_url = f"{WP_URL}/wp-json/wp/v2/media/{media_id}"
            meta_payload = {
                'title': draft_data.get('image_title'),
                'alt_text': draft_data.get('image_alt_text'),
                'caption': draft_data.get('image_title') # Often good to set caption too
            }
            meta_response = requests.post(
                update_media_url, 
                headers={'User-Agent': 'Mozilla/5.0'}, 
                json=meta_payload, 
                auth=auth_tuple
            )
            if meta_response.status_code == 200:
                log_terminal(f"✅ Successfully updated metadata for Media ID: {media_id}")
            else:
                log_terminal(f"⚠️  Could not update metadata for Media ID: {media_id}. Status: {meta_response.status_code}")

        except requests.exceptions.RequestException as e:
            log_terminal("--- ❌ IMAGE UPLOAD FAILED: Detailed Server Response ---")
            if e.response is not None:
                log_terminal(f"    - Status Code: {e.response.status_code}")
                log_terminal(f"    - Headers: {e.response.headers}")
                log_terminal(f"    - Body: {e.response.text}")
            log_terminal("---------------------------------------------------------")
            raise

        # 2. Get Category and Tag IDs
        category_id = get_or_create_term(draft_data.get('post_category'), 'categories', WP_URL, auth_tuple)
        tag_ids = [tid for tid in [get_or_create_term(tag, 'tags', WP_URL, auth_tuple) for tag in draft_data.get('post_tags', [])] if tid is not None]

        # 3. Prepare Post Payload
        post_payload = {
            'title': draft_data['post_title'],
            'content': draft_data['post_content_html'],
            'status': 'draft',
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

        # 4. Create or Update Post
        existing_post_id = draft_data.get('wordpress_post_id')
        post_headers = {'User-Agent': 'Mozilla/5.0'}
        if existing_post_id:
            log_terminal(f"📝 Updating existing post (ID: {existing_post_id}) in WordPress...")
            post_url = f"{WP_URL}/wp-json/wp/v2/posts/{existing_post_id}"
            post_response = requests.post(post_url, headers=post_headers, json=post_payload, auth=auth_tuple, timeout=30)
        else:
            log_terminal("📝 Creating new post in WordPress...")
            post_url = f"{WP_URL}/wp-json/wp/v2/posts"
            post_response = requests.post(post_url, headers=post_headers, json=post_payload, auth=auth_tuple, timeout=30)
        
        post_response.raise_for_status()
        response_data = post_response.json()
        log_terminal(f"✅ Post published successfully! URL: {response_data['link']}")

        # 5. Update local draft
        draft_data['status'] = 'published'
        draft_data['wordpress_post_id'] = response_data['id']
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
    if not url: raise HTTPException(status_code=400, detail="URL is required.")
    job_id = f"preview_{uuid.uuid4().hex[:10]}"
    generate_preview_task.delay(job_id, url)
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
    job_status = {
        "job_id": job_id, "project_id": project_id,
        "project_name": project_data.get("project_name"),
        "status": "starting", "total_urls": 0, "processed_urls": 0,
        "results": [], "started_at": datetime.now(timezone.utc).isoformat()
    }
    redis_client.set(f"job:{job_id}", json.dumps(job_status))
    run_project_task.delay(
        job_id,
        project_data,
        target_date=options.target_date,
        limit=options.limit
    )
    log_terminal(f"🚀 Kicked off new run for project '{project_data.get('project_name')}'. Job ID: {job_id}")
    return {"message": "Project run started successfully.", "job_id": job_id}

@app.get("/api/jobs/status/{job_id}")
async def get_run_status(job_id: str):
    job_json = redis_client.get(f"job:{job_id}")
    if not job_json:
        job_json = redis_client.get(job_id)
        if not job_json: raise HTTPException(status_code=404, detail="Job not found.")
    return json.loads(job_json)
