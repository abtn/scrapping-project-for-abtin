import requests
from celery import Celery
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from src.config import settings
from src.database.connection import SessionLocal
from src.database.models import ScrapedData, Source, ScrapedLog
from src.scraper.compliance import is_allowed





app = Celery('scraper', broker=settings.REDIS_URL)

def log_event(db, level, message, task_id=None, url=None):
    """Helper to write logs to the database"""
    try:
        log = ScrapedLog(
            level=level,
            message=str(message)[:500], # Truncate long errors
            task_id=task_id,
            url=url
        )
        db.add(log)
        db.commit()
    except Exception as e:
        print(f"FAILED TO LOG TO DB: {e}")
        db.rollback()

@app.task(bind=True) # bind=True gives us access to self.request.id
def scrape_task(self, url):
    task_id = self.request.id
    print(f"👨‍🍳 Chef is starting: {url}")
    
    # 0. Setup DB Session
    db = SessionLocal()

    try:
        # --- NEW: SOURCE REGISTRATION ---
        parsed = urlparse(url)
        domain = parsed.netloc
        
        # Try to find source, or create it
        source = db.query(Source).filter(Source.domain == domain).first()
        if not source:
            try:
                # Create if not exists
                source = Source(
                    domain=domain,
                    robots_url=f"{parsed.scheme}://{domain}/robots.txt",
                    last_crawled=datetime.utcnow()
                )
                db.add(source)
                db.commit()
                db.refresh(source)
            except IntegrityError:
                db.rollback()
                # Race condition handled: fetch it again
                source = db.query(Source).filter(Source.domain == domain).first()
                        # Update timestamp (VS Code fix: assert source is not None)
        if source:
            source.last_crawled = datetime.utcnow() # pyright: ignore
            db.commit()
        # -------------------------------

        # 1. Check Compliance
        if not is_allowed(url):
            msg = f"Blocked by robots.txt: {url}"
            print(f"⛔ {msg}")
            log_event(db, "WARN", msg, task_id, url)
            return "Blocked"

        # 2. Fetch Data
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            msg = f"Failed to download: {response.status_code}"
            log_event(db, "ERROR", msg, task_id, url)
            return "Failed"

        # 3. Parse Data
        soup = BeautifulSoup(response.text, 'html.parser')
        page_title = soup.title.string if soup.title else "No Title"
        
        headings = [h.get_text(strip=True) for h in soup.find_all('h2')]
        links = [a['href'] for a in soup.find_all('a', href=True) if 'http' in a['href']]
        
        rich_content = {
            "status": "success",
            "scraped_at": str(response.elapsed.total_seconds()) + "s",
            "headings": headings[:5],
            "links_found": len(links),
            "sample_links": links[:5]
        }

        # 4. Save to Database (Upsert)
        existing_record = db.query(ScrapedData).filter(ScrapedData.url == url).first()
        
        # Safe access to source.id
        source_id_val = source.id if source else None
        
        if existing_record:
            # Update
            db.query(ScrapedData).filter(ScrapedData.url == url).update({
                "title": page_title,
                "content": rich_content,
                "source_id": source_id_val  # Link to Source
            })
            log_event(db, "INFO", f"Updated data for {domain}", task_id, url)
        else:
            # Insert
            new_data = ScrapedData(
                url=url,
                title=page_title,
                content=rich_content,
                source_id=source_id_val # Link to Source
            )
            db.add(new_data)
            log_event(db, "INFO", f"Created new data for {domain}", task_id, url)
        
        db.commit()
        return "Success"

    except Exception as e:
        db.rollback()
        print(f"🔥 KITCHEN FIRE: {e}")
        log_event(db, "ERROR", f"Exception: {e}", task_id, url)
        return "Error"
    finally:
        db.close()