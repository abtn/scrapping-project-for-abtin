from fastapi.testclient import TestClient
from src.api.main import app

# Create a test client (like a fake web browser)
client = TestClient(app)

def test_health_check():
    """
    Verifies the API is running and returns the correct health message.
    """
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "Scraper API is running"}

def test_get_docs():
    """
    Verifies the Swagger UI endpoint is reachable.
    """
    response = client.get("/docs")
    assert response.status_code == 200