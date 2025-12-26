from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class Source(Base):
    __tablename__ = 'sources'
    id = Column(Integer, primary_key=True)
    domain = Column(String(255), unique=True, nullable=False)
    robots_url = Column(String(255))
    last_crawled = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship: One Source has many ScrapedData entries
    scraped_data = relationship("ScrapedData", back_populates="source")

class ScrapedLog(Base):
    __tablename__ = 'logs'
    id = Column(Integer, primary_key=True)
    level = Column(String(50)) # INFO, ERROR, WARN
    task_id = Column(String)   # Celery Task ID
    url = Column(String)
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class ScrapedData(Base):
    __tablename__ = 'scraped_data'
    id = Column(Integer, primary_key=True)
    
    # Link to Source (Optional for now, nullable=True)
    source_id = Column(Integer, ForeignKey('sources.id'), nullable=True)
    source = relationship("Source", back_populates="scraped_data")

    url = Column(String, unique=True, nullable=False)
    title = Column(String)
    content = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)