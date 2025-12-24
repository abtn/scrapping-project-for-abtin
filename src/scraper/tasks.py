import requests 
from bs4 import BeautifulSoup  # type: ignore
from sqlalchemy.exc import IntegrityError  # type: ignore
from celery import Celery
from src.config import settings
from src.database.models import ScrapedData
from src.database.connection import SessionLocal
from src.scraper.compliance import is_allowed


app = Celery('scraper', broker=settings.REDIS_URL)
# Use aiohttp to fetch a simple page (e.g., https://example.com).

@app.task
def scrape_task(url):
    print(f"👨‍🍳 Chef is starting: {url}")

    # 1. Check Compliance
    if not is_allowed(url):
        print(f"⛔ STOP: Robots.txt forbids {url}")
        return "Blocked"

    try:
        # 2. Fetch the Data (Download HTML)
        # We use a fake user-agent so we don't look like a robot
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.google.com/"
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            print(f"❌ Failed to download: {response.status_code}")
            return "Failed"

        # 3. Parse the Data (BeautifulSoup)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract the page title, or use "No Title" if missing
        page_title = soup.title.string if soup.title else "No Title"
        
        # 4. Save to Database
        db = SessionLocal() # Open connection
        
        new_data = ScrapedData(
            url=url,
            title=page_title,
            content={"status": "success", "length": len(response.text)}
        )
        
        try:
            db.add(new_data)
            db.commit() # Save changes
            print(f"✅ DISH READY: Saved '{page_title}' to DB")
        except IntegrityError:
            db.rollback()
            print(f"⚠️ Duplicate found: {url} is already in DB")
        finally:
            db.close() # Close connection
            
        return "Success"

    except Exception as e:
        print(f"🔥 KITCHEN FIRE: {e}")
        return "Error"