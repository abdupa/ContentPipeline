import os
import json
import uuid
from datetime import datetime, timezone

from celery_app import app as celery_app
from shared_state import redis_client, log_terminal

# Import your project's specific helper modules for scraping and AI.
# We will assume these are created in subsequent steps.
# from .scraper_logic import scrape_dynamic_data
# from .ai_logic import generate_content_for_draft

# --- MOCK HELPER FUNCTIONS (to be replaced with your actual logic) ---
# This is a placeholder for your actual scraping logic.
def scrape_dynamic_data(target_url, rules):
    """
    Placeholder for your Playwright/BeautifulSoup scraping logic.
    It will take a URL and a set of rules and return the scraped data.
    """
    log_terminal(f"🤖 Mock Scraping: Pretending to scrape data from {target_url}")
    # In a real scenario, this would use Playwright to get the page
    # and then BeautifulSoup to extract data based on the rules.
    mock_specs = {rule['name']: f"Mock data for {rule['name']}" for rule in rules}
    mock_specs['phone_model'] = "Mock Phone Model" # Usually scraped from a title element
    return mock_specs

# This is a placeholder for your actual OpenAI/LLM logic.
def generate_content_for_draft(prompt, scraped_data):
    """
    Placeholder for your AI content generation logic.
    It takes a prompt template and the scraped data and returns the AI's response.
    """
    log_terminal(f"🧠 Mock AI Gen: Generating content with prompt: '{prompt[:50]}...'")
    # In a real scenario, this would format the prompt with scraped_data
    # and call the OpenAI API.
    return {
        "focus_keyphrase": f"{scraped_data.get('phone_model', 'phone')} specs",
        "seo_title": f"Complete Specs for {scraped_data.get('phone_model', 'New Phone')}",
        "meta_description": f"Find all the specs and details for the {scraped_data.get('phone_model', 'new phone')}.",
        "slug": f"{scraped_data.get('phone_model', 'new-phone').lower().replace(' ', '-')}-specs",
        "post_category": "Phones",
        "post_tags": ["tech", "smartphones", scraped_data.get('phone_model', 'phone')],
        "post_title": f"Full Specifications of the {scraped_data.get('phone_model', 'New Phone')}",
        "post_excerpt": f"An overview of the new {scraped_data.get('phone_model', 'New Phone')}.",
        "featured_image_prompt": f"A futuristic product shot of the {scraped_data.get('phone_model', 'New Phone')}, clean background",
        "image_alt_text": f"A studio shot of the {scraped_data.get('phone_model', 'New Phone')}",
        "image_title": f"{scraped_data.get('phone_model', 'New Phone')} specifications overview",
        "post_content_html": f"<h1>{scraped_data.get('phone_model', 'New Phone')} Specs</h1><p>Here is the detailed information...</p>"
    }
# --- END MOCK HELPERS ---


@celery_app.task(bind=True)
def run_phone_scraper_task(self, job_id: str, project_data: dict):
    """
    Celery task for the 'phone_spec_scraper' project type.
    This task iterates through a list of URLs, scrapes data based on saved rules,
    and creates two drafts (WooCommerce & WordPress) for each URL.
    """
    log_terminal(f"--- [PHONE SCRAPER] Starting job {job_id} for project: {project_data.get('project_name')} ---")
    
    config = project_data.get('scrape_config', {})
    # Use modelUrls which should be populated from the wizard's link selection/manual list
    urls_to_process = config.get('modelUrls', [])
    rules = config.get('element_rules', [])
    prompts = json.loads(project_data.get('llm_prompt_template', '{}'))

    if not urls_to_process:
        log_terminal(f"⚠️ Job {job_id} has no URLs to process. Completing.")
        # Update job status to complete
        return

    job_status = {
        "job_id": job_id, "project_id": project_data.get('project_id'),
        "project_name": project_data.get("project_name"),
        "status": "processing", "total_urls": len(urls_to_process), "processed_urls": 0,
        "results": [], "started_at": datetime.now(timezone.utc).isoformat()
    }
    redis_client.set(f"job:{job_id}", json.dumps(job_status))

    for url in urls_to_process:
        try:
            # 1. Scrape Data using rules from the project template
            scraped_data = scrape_dynamic_data(url, rules)
            phone_name = scraped_data.get('phone_model', 'Unknown Phone')

            # 2. Generate Content for Both Drafts
            woo_content = generate_content_for_draft(prompts.get('product_prompt', ''), scraped_data)
            wp_content = generate_content_for_draft(prompts.get('price_prompt', ''), scraped_data)

            # 3. Create Draft 1: WooCommerce Product
            woo_draft_id = f"draft_{uuid.uuid4().hex[:10]}"
            woo_draft_data = {
                "draft_id": woo_draft_id,
                "draft_type": "woocommerce_product",
                "status": "draft",
                "source_url": url,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "original_content": scraped_data,
                "llm_prompt_template": project_data.get('llm_prompt_template'),
                "content_history": [],
                "image_history": [],
                "wordpress_post_id": None,
                "featured_image_b64": None, # Image can be generated later in editor
                **woo_content # Unpack all the AI generated fields
            }
            # Add a more descriptive title for the queue
            woo_draft_data['post_title'] = f"[Product] {phone_name}"
            redis_client.set(f"draft:{woo_draft_id}", json.dumps(woo_draft_data))
            redis_client.sadd("drafts_set", woo_draft_id)
            log_terminal(f"✅ Created WooCommerce draft for {phone_name}")

            # 4. Create Draft 2: WordPress Price Post
            wp_draft_id = f"draft_{uuid.uuid4().hex[:10]}"
            wp_draft_data = {
                "draft_id": wp_draft_id,
                "draft_type": "wordpress_post",
                "status": "draft",
                "source_url": url,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "original_content": scraped_data,
                "llm_prompt_template": project_data.get('llm_prompt_template'),
                "content_history": [],
                "image_history": [],
                "wordpress_post_id": None,
                "featured_image_b64": None,
                **wp_content # Unpack all the AI generated fields
            }
            # Add a more descriptive title for the queue
            wp_draft_data['post_title'] = f"[Price Post] {phone_name}"
            redis_client.set(f"draft:{wp_draft_id}", json.dumps(wp_draft_data))
            redis_client.sadd("drafts_set", wp_draft_id)
            log_terminal(f"✅ Created WordPress draft for {phone_name}")

            # Update job progress
            job_status['processed_urls'] += 1
            job_status['results'].append({
                "source_url": url,
                "status": "Success",
                "notes": f"Created 2 drafts (Woo: {woo_draft_id}, WP: {wp_draft_id})"
            })
            redis_client.set(f"job:{job_id}", json.dumps(job_status))

        except Exception as e:
            log_terminal(f"❌ Error processing URL {url} in job {job_id}: {e}")
            job_status['processed_urls'] += 1
            job_status['results'].append({
                "source_url": url,
                "status": "Failed",
                "notes": str(e)
            })
            redis_client.set(f"job:{job_id}", json.dumps(job_status))
            continue

    # Finalize job
    job_status['status'] = 'complete'
    redis_client.set(f"job:{job_id}", json.dumps(job_status))
    log_terminal(f"🎉 Job {job_id} complete! Processed all URLs.")
