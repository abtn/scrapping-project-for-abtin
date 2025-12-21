from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.config import settings

# Create the engine using the URL from .env
engine = create_engine(settings.DB_URL)

# Create a Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()