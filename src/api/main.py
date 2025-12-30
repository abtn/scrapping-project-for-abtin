from fastapi import FastAPI, Depends, HTTPException, Query # type: ignore # import FastAPI and other dependencies
from sqlalchemy.orm import Session # import Session for database interactions
from typing import List # import List for type hinting

from src.database.connection import get_db # import the database session dependency
from src.database.models import ScrapedData # import the database models
from src.api.schemas import ArticleResponse, ArticleDetail # import the response schemas

app = FastAPI(title="Scraper API", version="1.0.0") # Initialize FastAPI app

@app.get("/")
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "message": "Scraper API is running"}

# 1. Get All Articles (Pagination included)
@app.get("/api/v1/articles", response_model=List[ArticleResponse])
def get_articles(
    skip: int = 0, 
    limit: int = 20, 
    db: Session = Depends(get_db)
):
    """
    Fetch a list of articles. 
    Does NOT return the full text to keep the response light.
    """
    articles = db.query(ScrapedData)\
        .order_by(ScrapedData.created_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()
    return articles

# 2. Get Single Article (With Full Text)
@app.get("/api/v1/articles/{article_id}", response_model=ArticleDetail)
def get_article_detail(article_id: int, db: Session = Depends(get_db)):
    """
    Fetch full details of a specific article including clean_text.
    """
    article = db.query(ScrapedData).filter(ScrapedData.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article