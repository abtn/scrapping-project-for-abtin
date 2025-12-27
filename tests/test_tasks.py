import pytest # type: ignore
from unittest.mock import MagicMock, patch
from src.scraper.tasks import scrape_task

# Shared mocks for success test
@patch('src.scraper.tasks.fetch_url')
@patch('src.scraper.tasks.is_allowed', return_value=True)
@patch('src.scraper.tasks.SessionLocal')
def test_scrape_task_success(mock_db, mock_allowed, mock_fetch):
    """
    Test the full flow: Compliance -> Fetch -> Parse -> Save
    """
    mock_fetch.return_value = ("<html></html>", "http://test.com")
    
    mock_session = MagicMock()
    mock_db.return_value = mock_session
    # Mock source/data queries to return None (Simulate new insert)
    mock_session.query.return_value.filter.return_value.first.return_value = None

    result = scrape_task.apply(args=["http://test.com/page"]).get() # type: ignore

    assert result == "Success"
    assert mock_session.add.called

# FIX: Added SessionLocal mock to this test too
@patch('src.scraper.tasks.SessionLocal')  # <--- NEW MOCK
@patch('src.scraper.tasks.is_allowed', return_value=False)
def test_scrape_task_blocked(mock_allowed, mock_db):
    """
    Test that the task exits early if robots.txt disallows.
    """
    # Even if blocked, the code tries to query the Source table first.
    # We allow the DB mock to handle that silently.
    
    result = scrape_task.apply(args=["http://blocked.com"]).get() # type: ignore
    
    assert result == "Blocked"
    mock_allowed.assert_called_once()