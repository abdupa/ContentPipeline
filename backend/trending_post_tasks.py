import os
import json
import uuid
from datetime import datetime
from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin

from celery_app import app as celery_app
from shared_state import redis_client, log_terminal

# --- Constants ---
GSMARENA_URL = "https://www.gsmarena.com/"

# --- Helper Functions ---

def get_current_week_and_year():
    """Calculates the current ISO week number and year."""
    now = datetime.now()
    iso_cal = now.isocalendar()
    return iso_cal.week, iso_cal.year

def scrape_trending_phones():
    """Scrapes the top 10 trending phones from the GSMArena homepage."""
    log_terminal("📈 Scraping GSMArena for top 10 trending phones...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(GSMARENA_URL, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # This selector targets the specific container for the trending phones list
        trending_container = soup.select_one(".module-phones-list")
        if not trending_container:
            raise ValueError("Could not find the trending phones container on the homepage.")
            
        phone_links = trending_container.find_all("a", class_="module-phones-link")
        
        trending_list = []
        for link in phone_links[:10]: # Ensure we only take the top 10
            name = link.get_text(strip=True)
            partial_url = link.get('href')
            full_url = urljoin(GSMARENA_URL, partial_url)
            trending_list.append({"name": name, "url": full_url})
            
        log_terminal(f"✅ Found {len(trending_list)} trending phones.")
        return trending_list

    except requests.RequestException as e:
        log_terminal(f"❌ Failed to fetch GSMArena homepage: {e}")
        return []
    except Exception as e:
        log_terminal(f"❌ An error occurred during trending phones scraping: {e}")
        return []

def enrich_phone_data(trending_phones: list, product_db: list):
    """
    Enriches the scraped phone list with key specs from the local product database.
    This is a mock function. In a real scenario, you'd perform a more robust lookup.
    """
    log_terminal("🔍 Enriching phone data from local product database...")
    enriched_list = []
    for phone in trending_phones:
        # Mock enrichment - in a real app, you'd search product_db for a match
        enriched_phone = {
            **phone,
            "trend_highlight": "📈 Midrange Favorite", # Mock data
            "key_specs": "Mock Chipset, AMOLED 120Hz, 5000mAh", # Mock data
            "est_price": "₱25,000" # Mock data
        }
        enriched_list.append(enriched_phone)
    return enriched_list

# --- Main Celery Task ---

@celery_app.task(bind=True)
def generate_weekly_trending_post_task(self, job_id: str, project_data: dict):
    """
    Celery task for the 'weekly_trending_post' project type.
    This task scrapes the latest trending phones, enriches the data,
    briefs the AI using a master prompt, and creates a single draft.
    """
    log_terminal(f"--- [WEEKLY TRENDING POST] Starting job {job_id} ---")
    
    try:
        # 1. Get Current Time & Scrape Data
        week, year = get_current_week_and_year()
        trending_phones_raw = scrape_trending_phones()
        if not trending_phones_raw:
            raise ValueError("Scraping returned no phones. Aborting task.")

        # 2. Enrich Data (using a mock product_db for now)
        # In a real scenario, this would load your actual product_database.json
        mock_product_db = [{"name": p["name"], "specs": "..."} for p in trending_phones_raw]
        enriched_phones = enrich_phone_data(trending_phones_raw, mock_product_db)

        # 3. Prepare AI Inputs from Enriched Data
        # Create the detailed Top 10 list as a Markdown string
        top_10_list_md = ""
        for i, phone in enumerate(enriched_phones, 1):
            top_10_list_md += f"{i}. {phone['name']} – {phone['trend_highlight']}\n"
            top_10_list_md += f"   Key Highlight: {phone['key_specs']}\n"
            top_10_list_md += f"   👉 Browse {phone['name']} Full Specs\n\n"
        
        # Create the summary table as an HTML string
        summary_table_html = "<table><thead><tr><th>Model</th><th>Trend Highlight</th><th>Key Specs</th><th>Est. Price (PHP)</th></tr></thead><tbody>"
        for phone in enriched_phones:
            summary_table_html += f"<tr><td>{phone['name']}</td><td>{phone['trend_highlight']}</td><td>{phone['key_specs']}</td><td>{phone['est_price']}</td></tr>"
        summary_table_html += "</tbody></table>"

        # 4. Brief the AI using the Master Prompt
        master_prompt = project_data.get('llm_prompt_template', '')
        final_prompt = master_prompt.replace('[current_week]', str(week))
        final_prompt = final_prompt.replace('[current_year]', str(year))
        final_prompt = final_prompt.replace('[top_10_list]', top_10_list_md)
        final_prompt = final_prompt.replace('[summary_table_html]', summary_table_html)
        # You would add more replacements for other placeholders like [key_trends_summary]

        log_terminal("🤖 Briefing AI with the master prompt...")
        # This is where you would make the actual call to the OpenAI API
        # For now, we'll use the master prompt itself as the mock response.
        mock_ai_response_html = final_prompt 

        # 5. Save the result as a single draft
        draft_id = f"draft_{uuid.uuid4().hex[:10]}"
        post_title = f"Trending Phones {year} Week {week} – Top 10 Picks"
        
        draft_data = {
            "draft_id": draft_id,
            "draft_type": "wordpress_post", # This is a standard blog post
            "status": "draft",
            "source_url": GSMARENA_URL,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "original_content": {"trending_phones": enriched_phones},
            "llm_prompt_template": master_prompt,
            "content_history": [], "image_history": [],
            "wordpress_post_id": None, "featured_image_b64": None,
            "post_title": post_title,
            "post_content_html": mock_ai_response_html,
            # Add default/mock metadata
            "focus_keyphrase": f"trending phones {year} week {week}",
            "seo_title": post_title,
            "meta_description": f"Discover the top 10 trending phones for week {week} of {year}.",
            "slug": f"trending-phones-{year}-week-{week}",
            "post_category": "News",
            "post_tags": ["trending phones", "top 10", f"week {week}"],
            "post_excerpt": f"A summary of the most popular phones for week {week} of {year}.",
            "featured_image_prompt": f"A futuristic grid of the top 10 most popular smartphones for week {week} {year}",
            "image_alt_text": f"Top 10 trending phones for week {week} {year}",
            "image_title": f"Trending Phones {year} Week {week}",
        }
        
        redis_client.set(f"draft:{draft_id}", json.dumps(draft_data))
        redis_client.sadd("drafts_set", draft_id)
        log_terminal(f"✅ Saved new weekly trending post as draft: {draft_id}")

        # Update job status to complete
        job_status = {
            "job_id": job_id, "status": "complete",
            "results": [{"title": post_title, "status": "Generated", "notes": f"Saved as draft: {draft_id}"}]
        }
        redis_client.set(f"job:{job_id}", json.dumps(job_status))

    except Exception as e:
        log_terminal(f"❌ Job {job_id} FAILED: {e}")
        job_status = {"job_id": job_id, "status": "failed", "error": str(e)}
        redis_client.set(f"job:{job_id}", json.dumps(job_status))

