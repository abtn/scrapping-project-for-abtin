import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Use localhost because Python runs in WSL and connects to Docker via mapped ports
    DB_URL = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    REDIS_URL = os.getenv('REDIS_URL')

settings = Settings()