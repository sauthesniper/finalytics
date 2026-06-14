from app.filters import is_blocked_domain
from app.scoring import score_candidate
from app.search import search_web
from app.utils import extract_domain


MIN_CONFIDENCE = 0.5


def discover_company_website(company_name: str) -> dict:
    search_results = search_web(company_name)

    candidates = []

    for position, result in enumerate(search_results):
        title = result.get("title", "")
        url = result.get("url", "")

        if not url:
            continue

        domain = extract_domain(url)

        if is_blocked_domain(domain):
            continue

        score = score_candidate(company_name, title, url, position)

        candidates.append({
            "title": title,
            "url": url,
            "domain": domain,
            "score": score
        })

    candidates.sort(
        key=lambda candidate: candidate["score"],
        reverse=True
    )

    if not candidates:
        return {
            "companyName": company_name,
            "website": None,
            "domain": None,
            "confidence": 0.0,
            "status": "not_found",
            "alternatives": [],
            "error": "No reliable website candidate found."
        }

    best_candidate = candidates[0]

    if best_candidate["score"] < MIN_CONFIDENCE:
        return {
            "companyName": company_name,
            "website": None,
            "domain": None,
            "confidence": best_candidate["score"],
            "status": "not_found",
            "alternatives": candidates[:5],
            "error": "No candidate passed the minimum confidence threshold."
        }

    return {
        "companyName": company_name,
        "website": best_candidate["url"],
        "domain": best_candidate["domain"],
        "confidence": best_candidate["score"],
        "status": "found",
        "alternatives": candidates[:5],
        "error": None
    }