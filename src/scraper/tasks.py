from celery import Celery
from src.config import settings
from src.scraper.compliance import is_allowed

app = Celery('scraper', broker=settings.REDIS_URL)

@app.task
def scrape_task(url):
    if not is_allowed(url):
        return f"Blocked by robots.txt: {url}"
    
    # Placeholder for scraping logic
    print(f"Scraping {url}...")
    return f"Scraped {url}"