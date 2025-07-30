import uuid
import json
from io import StringIO
import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from shared_state import redis_client, log_terminal
from tasks import process_single_row_task
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from pathlib import Path
import shutil
from playwright.async_api import async_playwright
from tasks import generate_preview_task



app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://192.168.1.101:5173"  # <-- Add this line
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REQUIRED_COLUMNS = [
    'Post Title', 'Primary Keywords', 'Purpose', 'Homepage Link Text', 
    'Homepage Internal Link', 'Pillar Link Text', 'Pillar Page Internal Link', 
    'Image Prompt', 'Category', 'Schedule'
]

@app.post("/upload-and-analyze/")
async def upload_and_analyze(file: UploadFile = File(...)):
    """
    NEW LOGIC: Reads, validates, and stages the CSV data in Redis 
    without starting the processing tasks.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV.")

    job_id = f"job_{uuid.uuid4().hex[:10]}"
    contents = await file.read()
    
    try:
        df = pd.read_csv(StringIO(contents.decode('utf-8')))
        df = df.astype(object).where(pd.notnull(df), None) # Sanitize NaN values
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading CSV file: {e}")

    # --- Validation Logic ---
    actual_headers = df.columns.tolist()
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in actual_headers]
    validation_errors = []
    if missing_columns:
        validation_errors.append(f"Missing required columns: {', '.join(missing_columns)}")

    # Example of another validation: Check for empty "Post Title"
    for index, row in df.iterrows():
        if not row.get('Post Title'):
            validation_errors.append(f"Row {index + 2}: 'Post Title' cannot be empty.")
    
    # --- Staging in Redis ---
    job_status = "validated" if not validation_errors else "validation_failed"
    job_data = {
        "job_id": job_id,
        "status": job_status,
        "total_rows": len(df),
        "processed_rows": 0,
        "data": df.to_dict(orient='records'),
        "results": []
    }
    
    redis_client.set(job_id, json.dumps(job_data))
    log_terminal(f"✅ Job '{job_id}' validated and staged with status: {job_status}")

    # --- Return the full analysis to the frontend ---
    return {
        "job_id": job_id,
        "fileName": file.filename,
        "totalRows": len(df),
        "requiredColumnsPresent": not missing_columns,
        "dataValidationErrors": validation_errors
    }


@app.post("/start-content-generation/{job_id}")
async def start_content_generation(job_id: str):
    """
    This endpoint now has the single responsibility of starting the tasks for a validated job.
    """
    job_json = redis_client.get(job_id)
    if not job_json:
        raise HTTPException(status_code=404, detail="Job not found.")

    job_data = json.loads(job_json)

    # Only start if the status is 'validated'
    if job_data["status"] == "validated":
        job_data["status"] = "processing"
        redis_client.set(job_id, json.dumps(job_data))
        
        all_rows = job_data.get("data", [])
        log_terminal(f"🚀 Kicking off processing for job '{job_id}'...")
        # Initialize the counter when the job starts
        redis_client.set(f"{job_id}:count", 0)
        for row_data in all_rows:
            process_single_row_task.delay(job_id, row_data)
        
        return {"message": f"Content generation started for job {job_id}"}
    
    # Handle cases where the job is not in a startable state
    if job_data["status"] == "processing":
        raise HTTPException(status_code=400, detail=f"Job {job_id} is already processing.")
    else:
        raise HTTPException(status_code=400, detail=f"Job {job_id} could not be started. Status: {job_data['status']}")


@app.get("/jobs/{job_id}/status")
async def get_job_status(job_id: str):
    job_json = redis_client.get(job_id)
    if not job_json:
        raise HTTPException(status_code=404, detail="Job not found.")
    
    job_data = json.loads(job_json)
    atomic_count = redis_client.get(f"{job_id}:count")
    if atomic_count:
        job_data["processed_rows"] = int(atomic_count)

    return job_data
    

# --- UPDATED ENDPOINT FOR PAGE PREVIEWS WITH DEBUGGING ---
@app.post("/api/get-page-preview/")
async def get_page_preview(payload: dict):
    url = payload.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required.")

    # --- NEW, MORE INTELLIGENT INJECTED SCRIPT ---
    injected_script = """
    <script>
        function generateCssSelector(el) {
            if (!(el instanceof Element)) return;
            const path = [];
            while (el.nodeType === Node.ELEMENT_NODE) {
                let selector = el.nodeName.toLowerCase();
                if (el.id) {
                    selector = '#' + el.id;
                    path.unshift(selector);
                    break; // ID is unique, no need to go further
                } else {
                    let sib = el, nth = 1;
                    while (sib = sib.previousElementSibling) {
                        if (sib.nodeName.toLowerCase() == selector)
                           nth++;
                    }
                    if (nth != 1)
                        selector += ":nth-of-type("+nth+")";
                }
                path.unshift(selector);
                el = el.parentNode;
            }
            return path.join(" > ");
        }

        document.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            const selector = generateCssSelector(e.target);
            window.parent.postMessage({
                type: 'element-selected',
                selector: selector
            }, '*');
        }, true);
    </script>
    """

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(args=["--no-sandbox"])
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
            await page.goto(url, wait_until='domcontentloaded', timeout=90000)
            await page.wait_for_timeout(3000)
            html_content = await page.content()
            await browser.close()

        final_html = html_content.replace('</body>', f'{injected_script}</body>')
        return {"html": final_html}
    except Exception as e:
        log_terminal(f"❌ Failed to fetch page preview for {url}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch page preview: {str(e)}")


# --- NEW ENDPOINT FOR STARTING THE SCRAPER WIZARD JOB ---
@app.post("/api/start-wizard-scrape")
async def start_wizard_scrape(payload: dict):
    """
    Accepts the new flexible scraping configuration from the wizard,
    creates a job record, and starts the background task.
    """
    scrape_type = payload.get("scrape_type")
    element_rules = payload.get("element_rules")
    job_id = f"scrape_job_{uuid.uuid4().hex[:10]}"
    job_data = {}
    
    # --- NEW: Validate based on the scrape_type ---
    if scrape_type == 'direct':
        model_urls = payload.get("modelUrls")
        if not all([model_urls, element_rules]):
            raise HTTPException(status_code=400, detail="Incomplete configuration for Direct Selection.")
        
        job_data["total_urls"] = len(model_urls)

    elif scrape_type == 'crawl':
        initial_urls = payload.get("initial_urls")
        crawling_levels = payload.get("crawling_levels")
        if not all([initial_urls, crawling_levels, element_rules]):
            raise HTTPException(status_code=400, detail="Incomplete configuration for Crawling Path.")
        
        # We don't know the total URLs yet for a crawl, so we can omit it or set to 0
        job_data["total_urls"] = 0 
    
    else:
        raise HTTPException(status_code=400, detail=f"Unknown scrape_type: {scrape_type}")

    # --- Staging the Job in Redis ---
    job_data.update({
        "job_id": job_id,
        "status": "processing",
        "processed_urls": 0,
        "config": payload, # Save the entire configuration payload
        "results": []
    })
    
    redis_client.set(job_id, json.dumps(job_data))
    log_terminal(f"✅ Scrape job '{job_id}' created for type '{scrape_type}'. Starting task...")

    from tasks import scrape_website_task
    scrape_website_task.delay(job_id)

    return {"message": "Scraping job started successfully.", "job_id": job_id}

# --- NEW ENDPOINTS FOR ASYNCHRONOUS PREVIEW GENERATION ---
@app.post("/api/request-page-preview/")
async def request_page_preview(payload: dict):
    """
    Accepts a URL, creates a job ID, and starts the background
    Celery task to generate the preview. Returns the job ID immediately.
    """
    url = payload.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required.")

    # Create a unique ID for this preview job
    job_id = f"preview_{uuid.uuid4().hex[:10]}"

    # Start the background task, passing it the job_id and the url
    generate_preview_task.delay(job_id, url)

    log_terminal(f"✅ Preview job '{job_id}' for URL '{url}' has been dispatched.")

    # Immediately return the job ID to the frontend
    return {"job_id": job_id}


@app.get("/api/get-preview-result/{job_id}")
async def get_preview_result(job_id: str):
    """
    Checks Redis for the result of the preview generation job.
    The frontend will call this endpoint repeatedly (poll).
    """
    result_json = redis_client.get(job_id)

    if not result_json:
        # If no key is found, the job is still pending
        return {"status": "pending"}

    result = json.loads(result_json)
    return result


@app.get("/api/get-scrape-job-status/{job_id}")
async def get_scrape_job_status(job_id: str):
    """
    Retrieves the status, progress, and results of a scraping job from Redis.
    """
    job_json = redis_client.get(job_id)
    if not job_json:
        raise HTTPException(status_code=404, detail="Job not found.")
    
    return json.loads(job_json)