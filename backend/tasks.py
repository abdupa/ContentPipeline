import os
import asyncio
import random
import re
import shutil
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError
from celery_app import app as celery_app 
from celery.signals import worker_process_init
from shared_state import log_terminal
from bs4 import BeautifulSoup

load_dotenv()

# --- User-Agent List ---
USER_AGENTS_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
]

# --- Define a path for the persistent browser profile ---
USER_DATA_DIR = Path("./browser_profile")

# --- Worker Initialization ---
@worker_process_init.connect
def init_worker(**kwargs):
    log_terminal("--- [WORKER INIT] Initializing for Twitter Scraper... ---")
    # No need to check for credentials anymore as login is manual
    log_terminal("✅ Worker initialized successfully.")

# --- The Twitter Scraper Task (for the server) ---

@celery_app.task(bind=True, name="scrape_twitter_profile")
def scrape_twitter_profile(self, profile_url: str):
    try:
        return asyncio.run(run_automated_scraper(self, profile_url))
    except Exception as e:
        log_terminal(f"❌ An unexpected error occurred in the main task: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        return {'status': 'FAILURE', 'error': str(e)}

async def run_automated_scraper(task, profile_url: str):
    proxy_list_str = os.getenv("PROXY_LIST")
    posts_data = []
    
    max_retries = 3
    for attempt in range(max_retries):
        log_terminal(f"🚀 Starting scrape attempt {attempt + 1}/{max_retries}...")
        
        proxy_server = None
        if proxy_list_str:
            proxies = proxy_list_str.split(',')
            proxy_server = random.choice(proxies).strip()

        async with async_playwright() as p:
            launch_options = {'headless': True}
            if proxy_server:
                launch_options['proxy'] = {"server": proxy_server}
                log_terminal(f"    - Using proxy: {proxy_server.split('@')[1]}")
            
            if not USER_DATA_DIR.exists():
                error_msg = "Browser profile not found. A manual login session must be created and uploaded first."
                log_terminal(f"❌ {error_msg}")
                task.update_state(state='FAILURE', meta={'error': error_msg})
                return {'status': 'FAILURE', 'error': error_msg}

            context = await p.chromium.launch_persistent_context(
                USER_DATA_DIR,
                **launch_options,
                user_agent=random.choice(USER_AGENTS_LIST),
                viewport={'width': 1920, 'height': 1080}
            )
            page = await context.new_page()
            
            try:
                log_terminal(f"➡️ Navigating to target profile: {profile_url}")
                await page.goto(profile_url)
                await page.wait_for_load_state("networkidle", timeout=30000)
                
                if "login" in page.url:
                    raise Exception("Session is invalid or expired. A new manual login is required.")

                log_terminal("✅ Successfully on profile page with active session.")
                
                task.update_state(state='PROGRESS', meta={'status': 'Scrolling timeline...'})
                tweet_selector = 'article[data-testid="tweet"]'
                await page.wait_for_selector(tweet_selector, timeout=20000)
                
                collected_tweets = set()
                while True:
                    current_tweets_html = [await tweet.inner_html() for tweet in await page.locator(tweet_selector).all()]
                    new_tweets_found = any(html not in collected_tweets for html in current_tweets_html)
                    for html in current_tweets_html: collected_tweets.add(html)
                    if not new_tweets_found: 
                        log_terminal("✅ No new posts found after scroll. End of timeline.")
                        break
                    log_terminal(f"    ... collected {len(collected_tweets)} unique posts. Scrolling...")
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(random.randint(2000, 3500))

                task.update_state(state='PROGRESS', meta={'status': 'Extracting posts...'})
                soup = BeautifulSoup("".join(list(collected_tweets)), 'html.parser')
                tweet_text_elements = soup.select('[data-testid="tweetText"]')
                for element in tweet_text_elements:
                    posts_data.append({"text": element.get_text(separator=' ', strip=True)})
                
                log_terminal(f"✅ Extracted {len(posts_data)} posts.")
                await context.close()
                return {'status': 'SUCCESS', 'count': len(posts_data), 'data': posts_data}

            except Exception as e:
                error_msg = f"Attempt {attempt + 1} failed: {e}"
                log_terminal(f"❌ {error_msg}")
                screenshot_path = f"error_screenshot_{task.request.id}_{attempt+1}.png"
                await page.screenshot(path=screenshot_path)
                log_terminal(f"📸 Saved screenshot of the error page to: {screenshot_path}")
                await context.close()
                if attempt == max_retries - 1:
                    log_terminal("❌ All scrape attempts failed.")
                    task.update_state(state='FAILURE', meta={'error': "All scrape attempts failed."})
                    return {'status': 'FAILURE', 'error': "All scrape attempts failed after multiple retries."}

# --- NEW: Standalone function for creating the manual session ---
async def create_manual_session():
    """
    Launches a visible browser for the user to log in manually.
    This function should be run locally, not on the server.
    """
    print("--- Starting Manual Login Session Creator ---")
    if USER_DATA_DIR.exists():
        print(f"⚠️ Deleting existing browser profile at '{USER_DATA_DIR}' to ensure a fresh save.")
        shutil.rmtree(USER_DATA_DIR)
        
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False, # <-- This makes the browser visible
            user_agent=random.choice(USER_AGENTS_LIST)
        )
        page = await context.new_page()

        try:
            print("\n1. A browser window has opened.")
            print("2. Please log in to your X/Twitter account.")
            print("3. Solve any CAPTCHAs or security challenges.")
            print("4. Once you are successfully logged in and see your home timeline, you can close this script (Ctrl+C).\n")
            
            await page.goto("https://x.com/login")
            
            # Wait indefinitely for the user to successfully log in and land on the home page
            await page.wait_for_url("https://x.com/home", timeout=0)
            
            print("✅ Login session successfully saved to the 'browser_profile' directory.")
            print("You can now close the browser and this script.")

        except Exception as e:
            print(f"\n❌ An error occurred: {e}")
        finally:
            await context.close()

if __name__ == "__main__":
    # This block allows you to run this script directly to create the session
    # e.g., `python backend/tasks.py`
    asyncio.run(create_manual_session())
