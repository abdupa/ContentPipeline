import uuid
from pydantic import BaseModel
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from celery.result import AsyncResult

# --- Import only the task and app instance you need ---
from tasks import scrape_twitter_profile
from celery_app import app as celery_app

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, you should restrict this to your frontend's domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic model for the Twitter scrape request ---
class ScrapeRequest(BaseModel):
    profile_url: str

# --- API Endpoints for the Twitter Scraper ---

@app.post("/api/v1/scrape-twitter")
def start_twitter_scrape(request: ScrapeRequest):
    """
    Receives a profile URL and dispatches a scraping task to the Celery worker.
    """
    task = scrape_twitter_profile.delay(request.profile_url)
    return {"task_id": task.id}

@app.get("/api/v1/task-status/{task_id}")
def get_task_status(task_id: str):
    """
    Returns the status and result of any Celery task by its ID.
    """
    task_result = AsyncResult(task_id, app=celery_app)
    
    response = {
        "task_id": task_id,
        "status": task_result.state,
        "result": task_result.result or task_result.info, # Return result if successful, or info/error if not
    }
    return response

# --- All other endpoints, models, and helpers from the original file have been removed for focus ---
