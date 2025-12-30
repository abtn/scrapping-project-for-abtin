from pydantic import BaseModel, ConfigDict # import ConfigDict for ORM mode support
from datetime import datetime
from typing import Optional # import Optional for optional fields

class ArticleResponse(BaseModel):
    # Basic article information - used in lists
    id: int
    url: str
    title: Optional[str] = None
    author: Optional[str] = None
    published_date: Optional[str] = None
    summary: Optional[str] = None
    main_image: Optional[str] = None
    created_at: datetime

    # Config to allow reading from SQLAlchemy models (ORM mode)
    model_config = ConfigDict(from_attributes=True)

class ArticleDetail(ArticleResponse):
    """Includes the full text - used when clicking into an article"""
    clean_text: Optional[str] = None