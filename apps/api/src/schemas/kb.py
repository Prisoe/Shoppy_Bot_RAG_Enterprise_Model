from pydantic import BaseModel, HttpUrl
from typing import Optional
from uuid import UUID
from datetime import datetime


class KBSourceCreate(BaseModel):
    title: str
    source_type: str  # url | file | shopify_help
    url: Optional[str] = None
    product_area: Optional[str] = "general"
    language: Optional[str] = "en"


class KBSourceOut(BaseModel):
    id: UUID
    title: str
    source_type: str
    url: Optional[str]
    status: str
    product_area: Optional[str]
    language: str
    version: int
    created_at: datetime
    error_message: Optional[str]

    class Config:
        from_attributes = True


class KBQueryRequest(BaseModel):
    query: str
    product_area: Optional[str] = None
    top_k: Optional[int] = 8


class KBChunkOut(BaseModel):
    chunk_id: str
    text: str
    metadata: dict
    score: float


class ShopifyScrapeRequest(BaseModel):
    max_pages: Optional[int] = 100
    sections: Optional[list[str]] = None
