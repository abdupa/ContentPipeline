import uuid
import json
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from shared_state import redis_client, log_terminal
from tasks import generate_preview_task, run_project_task
from data_tasks import update_product_database_task # <-- NEW: Import the data task

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Simplified for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models for Scraping Projects (No Changes) ---
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

# --- Pydantic Models for Draft Content (No Changes) ---
class Draft(BaseModel):
    draft_id: str
    status: str
    source_url: str
    generated_at: str
    original_content: dict
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

# --- NEW: API Endpoint for Data Management ---

@app.post("/api/data/refresh-products", status_code=202)
async def refresh_product_database():
    """
    Triggers a background task to refresh the internal product database
    from the configured data source (e.g., WooCommerce).
    """
    try:
        update_product_database_task.delay()
        message = "Accepted: Product database refresh task has been queued."
        log_terminal(f"✅ {message}")
        return {"message": message}
    except Exception as e:
        log_terminal(f"❌ Failed to queue product database refresh task: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue the refresh task.")


# --- Approval Queue Endpoints (No Changes) ---
@app.get("/api/drafts", response_model=List[Draft])
async def get_all_drafts():
    draft_ids = redis_client.smembers("drafts_set")
    if not draft_ids:
        return []
    draft_pipelines = redis_client.mget([f"draft:{did}" for did in draft_ids])
    drafts = [json.loads(d) for d in draft_pipelines if d]
    return drafts

@app.get("/api/drafts/{draft_id}", response_model=Draft)
async def get_draft(draft_id: str):
    draft_json = redis_client.get(f"draft:{draft_id}")
    if not draft_json:
        raise HTTPException(status_code=404, detail="Draft not found.")
    return json.loads(draft_json)

@app.put("/api/drafts/{draft_id}", response_model=Draft)
async def update_draft(draft_id: str, draft_data: Draft):
    if not redis_client.exists(f"draft:{draft_id}"):
        raise HTTPException(status_code=404, detail="Draft not found.")
    redis_client.set(f"draft:{draft_id}", draft_data.model_dump_json())
    log_terminal(f"💾 Draft '{draft_data.post_title}' (ID: {draft_id}) was updated.")
    return draft_data

@app.post("/api/drafts/{draft_id}/publish")
async def publish_draft(draft_id: str):
    draft_json = redis_client.get(f"draft:{draft_id}")
    if not draft_json:
        raise HTTPException(status_code=404, detail="Draft not found.")
    draft_data = json.loads(draft_json)
    log_terminal(f"📤 Publishing draft '{draft_data.get('post_title')}' to WordPress...")
    draft_data['status'] = 'published'
    redis_client.set(f"draft:{draft_id}", json.dumps(draft_data))
    redis_client.srem("drafts_set", draft_id)
    redis_client.sadd("published_set", draft_id)
    return {"message": "Draft published successfully (simulation)."}

# --- Preview Endpoints (No Changes) ---
@app.post("/api/request-page-preview/")
async def request_page_preview(payload: dict):
    url = payload.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required.")
    job_id = f"preview_{uuid.uuid4().hex[:10]}"
    generate_preview_task.delay(job_id, url)
    return {"job_id": job_id}

@app.get("/api/get-preview-result/{job_id}")
async def get_preview_result(job_id: str):
    result_json = redis_client.get(job_id)
    if not result_json:
        return {"status": "pending"}
    return json.loads(result_json)

# --- Scraping Project Endpoints (No Changes) ---
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
async def run_project(project_id: str):
    project_json = redis_client.get(f"project:{project_id}")
    if not project_json:
        raise HTTPException(status_code=404, detail="Project not found.")
    project_data = json.loads(project_json)
    job_id = f"run_{uuid.uuid4().hex[:10]}"
    job_status = {
        "job_id": job_id, "project_id": project_id,
        "project_name": project_data.get("project_name"),
        "status": "starting", "total_urls": 0, "processed_urls": 0,
        "results": [], "started_at": datetime.now(timezone.utc).isoformat()
    }
    redis_client.set(f"job:{job_id}", json.dumps(job_status))
    run_project_task.delay(job_id, project_data)
    log_terminal(f"🚀 Kicked off new run for project '{project_data.get('project_name')}'. Job ID: {job_id}")
    return {"message": "Project run started successfully.", "job_id": job_id}

# --- Generic Job Status Endpoint (No Changes) ---
@app.get("/api/jobs/status/{job_id}")
async def get_run_status(job_id: str):
    job_json = redis_client.get(f"job:{job_id}")
    if not job_json:
        job_json = redis_client.get(job_id)
        if not job_json:
            raise HTTPException(status_code=404, detail="Job not found.")
    return json.loads(job_json)
