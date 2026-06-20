from typing import List, Optional

from pydantic import BaseModel


class DiscoverRequest(BaseModel):
    companyName: str


class SearchRequest(BaseModel):
    query: str
    num: Optional[int] = 10


class SearchResultItem(BaseModel):
    title: str
    url: str


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResultItem]


class WebsiteCandidate(BaseModel):
    title: str
    url: str
    domain: str
    score: float


class DiscoverResponse(BaseModel):
    companyName: str
    website: Optional[str]
    domain: Optional[str]
    confidence: float
    status: str
    alternatives: List[WebsiteCandidate]
    error: Optional[str]