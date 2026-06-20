import os

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException

from app.findweb import discover_company_website
from app.requests import DiscoverRequest, DiscoverResponse


load_dotenv()

API_KEY = os.getenv("API_KEY")


app = FastAPI(
    title="Company Website Discovery API",
    version="1.0.0"
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