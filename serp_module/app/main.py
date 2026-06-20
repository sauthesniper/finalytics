import os

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.findweb import discover_company_website
from app.search import raw_search
from app.requests import (
    DiscoverRequest,
    DiscoverResponse,
    SearchRequest,
    SearchResponse,
)


load_dotenv()

API_KEY = os.getenv("API_KEY")


app = FastAPI(
    title="Company Website Discovery API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_api_key(x_api_key: str) -> None:
    if API_KEY is None:
        raise HTTPException(
            status_code=500,
            detail="API_KEY is not configured on the server."
        )

    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key."
        )


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.post("/discover", response_model=DiscoverResponse)
def discover(
    request: DiscoverRequest,
    x_api_key: str = Header(...)
):
    verify_api_key(x_api_key)

    return discover_company_website(request.companyName)


@app.post("/search", response_model=SearchResponse)
def search(
    request: SearchRequest,
    x_api_key: str = Header(...)
):
    """Raw web search for an arbitrary query — the tool used by the agentic agent."""
    verify_api_key(x_api_key)
    results = raw_search(request.query, request.num or 10)
    return {"query": request.query, "results": results}