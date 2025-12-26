# src/scraper/parsers.py
from bs4 import BeautifulSoup

def parse_generic(soup: BeautifulSoup) -> dict:
    """
    A generic parser that extracts title, headings, and links.
    """
    page_title = soup.title.string.strip() if soup.title else "No Title" # type: ignore
    
    headings = [h.get_text(strip=True) for h in soup.find_all('h2')]
    links = [a['href'] for a in soup.find_all('a', href=True) if 'http' in a['href']]
    
    return {
        "title": page_title,
        "headings": headings[:5],
        "links_found": len(links),
        "sample_links": links[:5]
    }