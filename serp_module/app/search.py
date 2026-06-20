import os

import requests
from dotenv import load_dotenv


load_dotenv()

SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")


def raw_search(query: str, num: int = 10) -> list[dict]:
    """Run a raw Google search for an arbitrary query (used by the agentic tool)."""
    if SERPAPI_API_KEY is None:
        raise RuntimeError("SERPAPI_API_KEY is not configured.")

    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_API_KEY,
        "num": num,
        "hl": "ro",
        "gl": "ro",
    }

    response = requests.get(
        "https://serpapi.com/search",
        params=params,
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()

    results = []
    for item in data.get("organic_results", []):
        title = item.get("title")
        link = item.get("link")
        if not title or not link:
            continue
        results.append({"title": title, "url": link})

    return results


def search_web(company_name: str) -> list[dict]:
    if SERPAPI_API_KEY is None:
        raise RuntimeError("SERPAPI_API_KEY is not configured.")

    query = f"{company_name} official website"

    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_API_KEY,
        "num": 10,
        "hl": "en",
        "gl": "us"
    }

    response = requests.get(
        "https://serpapi.com/search",
        params=params,
        timeout=20
    )

    response.raise_for_status()

    data = response.json()

    organic_results = data.get("organic_results", [])

    results = []

    for item in organic_results:
        title = item.get("title")
        link = item.get("link")

        if not title or not link:
            continue

        results.append({
            "title": title,
            "url": link
        })

    return results