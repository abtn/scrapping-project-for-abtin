from src.database.models import Base
from sqlalchemy import create_engine
from src.config import settings

engine = create_engine(settings.DB_URL)
Base.metadata.create_all(engine)
print("Tables created successfully.")