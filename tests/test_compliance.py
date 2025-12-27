from src.scraper.compliance import is_allowed

def test_robots_allowed(mocker):
    """
    Test that is_allowed returns True when robots.txt permits it.
    """
    # FIX: Patch the object inside 'src.scraper.compliance', not 'urllib.robotparser'
    mock_parser = mocker.patch('src.scraper.compliance.RobotFileParser')
    
    # Setup the mock instance behavior
    instance = mock_parser.return_value
    instance.can_fetch.return_value = True
    
    # Run
    result = is_allowed("https://example.com/page")
    
    # Assert
    assert result is True
    instance.read.assert_called_once()

def test_robots_disallowed(mocker):
    """
    Test that is_allowed returns False when robots.txt forbids it.
    """
    # FIX: Patch the object inside 'src.scraper.compliance'
    mock_parser = mocker.patch('src.scraper.compliance.RobotFileParser')
    
    instance = mock_parser.return_value
    instance.can_fetch.return_value = False
    
    result = is_allowed("https://example.com/private")
    
    assert result is False