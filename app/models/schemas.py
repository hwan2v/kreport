from pydantic import BaseModel, Field
from typing import List, Any, Dict

class Doc(BaseModel):
    id: str
    title: str
    body: str

class SearchRequest(BaseModel):
    q: str = Field(default="*", description="쿼리")
    size: int = 10

class SearchHit(BaseModel):
    _id: str
    _score: float | None = None
    source: Dict[str, Any]

class SearchResponse(BaseModel):
    hits: List[SearchHit]

class ReportCreateRequest(BaseModel):
    query: str | None = None
