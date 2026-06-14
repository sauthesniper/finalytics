from app.utils import (
    company_name_tokens,
    domain_without_tld,
    extract_domain,
    normalize_text
)


def score_candidate(company_name: str, title: str, url: str, position: int) -> float:
    domain = extract_domain(url)
    domain_name = domain_without_tld(domain)

    tokens = company_name_tokens(company_name)

    title_normalized = normalize_text(title)
    domain_normalized = normalize_text(domain_name)
    url_normalized = normalize_text(url)

    score = 0.0

    if not tokens:
        return 0.0

    matched_domain_tokens = 0
    matched_title_tokens = 0

    for token in tokens:
        if token in domain_normalized:
            matched_domain_tokens += 1

        if token in title_normalized:
            matched_title_tokens += 1

        if token in url_normalized:
            score += 0.05

    domain_match_ratio = matched_domain_tokens / len(tokens)
    title_match_ratio = matched_title_tokens / len(tokens)

    score += domain_match_ratio * 0.45
    score += title_match_ratio * 0.30

    if "official" in title_normalized or "official" in url_normalized:
        score += 0.10

    if "home" in title_normalized:
        score += 0.05

    if position == 0:
        score += 0.10
    elif position == 1:
        score += 0.07
    elif position == 2:
        score += 0.04

    if score > 1.0:
        score = 1.0

    return round(score, 2)