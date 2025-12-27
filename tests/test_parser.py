from bs4 import BeautifulSoup
from src.scraper.parsers import parse_generic

def test_parse_generic_valid():
    """
    Test extraction of title, headings, and links from valid HTML.
    """
    html = """
    <html>
        <head><title>Test Page Title</title></head>
        <body>
            <h2>First Heading</h2>
            <h2>Second Heading</h2>
            <a href="http://example.com/1">Link 1</a>
            <a href="http://example.com/2">Link 2</a>
            <a href="/relative">Relative Link</a>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    data = parse_generic(soup)
    
    # Assertions
    assert data['title'] == "Test Page Title"
    assert len(data['headings']) == 2
    assert "First Heading" in data['headings']
    
    # Should count absolute links only (based on your parser logic)
    assert data['links_found'] == 2 
    assert "http://example.com/1" in data['sample_links']

def test_parse_generic_empty():
    """
    Test handling of empty or malformed HTML.
    """
    soup = BeautifulSoup("", 'html.parser')
    data = parse_generic(soup)
    
    assert data['title'] == "No Title"
    assert data['links_found'] == 0