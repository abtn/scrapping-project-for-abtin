import trafilatura # type: ignore
import json
from bs4 import BeautifulSoup

def parse_smart(html_content: str, url: str) -> dict:
    """
    Uses Trafilatura to extract the 'meat' of the article.
    Falls back to BeautifulSoup for basic metadata if Trafilatura fails.
    """
    # 1. Trafilatura Extraction (The Heavy Lifting)
    # include_comments=False, include_tables=False for cleaner text
    extracted = trafilatura.extract(
        html_content, 
        url=url,
        include_images=True,
        include_links=False,
        output_format='json',
        with_metadata=True
    )

    data = {}
    
    if extracted:
        try:
            t_data = json.loads(extracted)
            
            data['title'] = t_data.get('title')
            data['author'] = t_data.get('author')
            data['published_date'] = t_data.get('date')
            data['clean_text'] = t_data.get('text')
            data['main_image'] = t_data.get('image')
            
            # Generate a summary if excerpt isn't available
            text_body = t_data.get('text', '')
            excerpt = t_data.get('excerpt')
            data['summary'] = excerpt if excerpt else (text_body[:200] + "..." if len(text_body) > 200 else text_body)
        except json.JSONDecodeError:
            # Trafilatura returned something that isn't valid JSON (rare)
            pass
    
    # 2. Fallback / Augmentation (BeautifulSoup)
    # Sometimes Trafilatura misses the title or we want specific tags
    if not data.get('title'):
        soup = BeautifulSoup(html_content, 'html.parser')
        data['title'] = soup.title.get_text(strip=True) if soup.title else "No Title"

    return data