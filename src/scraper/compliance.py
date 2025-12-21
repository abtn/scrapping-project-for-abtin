from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse

def is_allowed(target_url, user_agent="MyBot/1.0"):
    try:
        parsed = urlparse(target_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(user_agent, target_url)
    except Exception as e:
        print(f"Robots.txt check failed: {e}")
        return True # Fail open or closed depending on policy