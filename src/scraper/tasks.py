import random
import requests
from celery import Celery
from celery.schedules import crontab
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config import settings
from src.scraper.compliance import is_allowed
from src.scraper.parsers import parse_smart
from src.database.connection import SessionLocal
from src.database.models import ScrapedData, Source, ScrapedLog, ScheduledJob

app = Celery('scraper', broker=settings.REDIS_URL)

# --- HELPER: Database Logging ---
def log_event(db, level, message, task_id=None, url=None):
    try:
        log = ScrapedLog(
            level=level,
            message=str(message)[:500],
            task_id=task_id,
            url=url
        )
        db.add(log)
        db.commit()
    except Exception as e:
        print(f"FAILED TO LOG TO DB: {e}")
        db.rollback()

# --- HELPER: Fetcher with Retries ---
USER_AGENTS = getattr(settings, 'USER_AGENTS', [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
])

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.RequestException)
)
def fetch_url(session, url):
    """
    Standard requests fetch, but 'magically' async thanks to Gevent.
    """
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    
    # Use the passed session for connection pooling
    response = session.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    return response.text, response.url

# --- CORE LOGIC ---
@app.task(bind=True) 
def scrape_task(self, url):
    task_id = self.request.id
    print(f"👨‍🍳 Chef is starting: {url}")
    
    db = SessionLocal()

    try:
        # --- SOURCE REGISTRATION ---
        parsed = urlparse(url)
        domain = parsed.netloc
        
        source = db.query(Source).filter(Source.domain == domain).first()
        if not source:
            try:
                source = Source(
                    domain=domain,
                    robots_url=f"{parsed.scheme}://{domain}/robots.txt",
                    last_crawled=datetime.now(timezone.utc)
                )
                db.add(source)
                db.commit()
                db.refresh(source)
            except IntegrityError:
                db.rollback()
                source = db.query(Source).filter(Source.domain == domain).first()
        
        if source:
            source.last_crawled = datetime.now(timezone.utc) # type: ignore
            db.commit()
        # ---------------------------

        # 1. Check Compliance
        if not is_allowed(url):
            msg = f"Blocked by robots.txt: {url}"
            print(f"⛔ {msg}")
            log_event(db, "WARN", msg, task_id, url)
            return "Blocked"

        # 2. Fetch Data (High Performance)
        try:
            with requests.Session() as session:
                html_content, final_url = fetch_url(session, url)
                
        except Exception as fetch_err:
            msg = f"Network Error: {fetch_err}"
            log_event(db, "ERROR", msg, task_id, url)
            return "Failed"

        # 3. Parse Data (Smart)
        extracted_data = parse_smart(html_content, final_url)
        
        rich_content = {
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "raw_metadata": extracted_data 
        }

        # 4. Save to Database (Upsert with New Columns)
        existing_record = db.query(ScrapedData).filter(ScrapedData.url == url).first()
        
        source_id_val = source.id if source else None
        
        # Define the data dictionary to be inserted/updated
        update_data = {
            "title": extracted_data.get('title'),
            "author": extracted_data.get('author'),
            "published_date": extracted_data.get('published_date'),
            "summary": extracted_data.get('summary'),
            "main_image": extracted_data.get('main_image'),
            "clean_text": extracted_data.get('clean_text'),
            "content": rich_content,
            "source_id": source_id_val
        }

        if existing_record:
            # Update existing record
            for key, value in update_data.items():
                setattr(existing_record, key, value)
            log_event(db, "INFO", f"Updated rich data for {domain}", task_id, url)
        else:
            # Create new record
            new_data = ScrapedData(
                url=url,
                **update_data 
            )
            db.add(new_data)
            log_event(db, "INFO", f"Created rich data for {domain}", task_id, url)
        
        db.commit()
        return "Success"

    except Exception as e:
        db.rollback()
        print(f"🔥 KITCHEN FIRE: {e}")
        log_event(db, "ERROR", f"Exception: {e}", task_id, url)
        return "Error"
    finally:
        db.close()

# --- SCHEDULER LOGIC ---
@app.task
def periodic_check_task():
    """
    Dynamic Manager: Queries scheduled_jobs table and executes based on interval.
    """
    print("⏰ [BEAT] Checking database for active schedules...")
    db = SessionLocal()
    try:
        # 1. Get all active jobs
        active_jobs = db.query(ScheduledJob).filter(ScheduledJob.is_active == True).all()
        
        now = datetime.now(timezone.utc)
        tasks_dispatched = 0
        
        for job in active_jobs:
            should_run = False
            
            # 2. Logic: Time math
            if job.last_triggered_at is None:
                should_run = True # Never ran before
            else:
                # Ensure we are comparing offset-aware datetimes
                last_run = job.last_triggered_at.replace(tzinfo=timezone.utc) if job.last_triggered_at.tzinfo is None else job.last_triggered_at
                delta = now - last_run
                
                if delta.total_seconds() >= job.interval_seconds:
                    should_run = True
            
            # 3. Dispatch
            if should_run:
                print(f"✅ [BEAT] Triggering job: {job.name} ({job.url})")
                scrape_task.delay(job.url) # type: ignore
                
                # Update timestamp
                job.last_triggered_at = now # type: ignore
                tasks_dispatched += 1
        
        if tasks_dispatched > 0:
            db.commit()
            return f"Dispatched {tasks_dispatched} tasks."
            
        return "No tasks due."

    except Exception as e:
        db.rollback()
        print(f"❌ [BEAT] Error: {e}")
        return "Error"
    finally:
        db.close()

# --- REPLACES OLD SCHEDULE ---
app.conf.beat_schedule = {
    'dynamic-dispatcher': {
        'task': 'src.scraper.tasks.periodic_check_task',
        'schedule': 60.0,  # Check the DB every 60 seconds
    },
}