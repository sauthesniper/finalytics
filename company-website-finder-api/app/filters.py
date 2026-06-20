BLOCKED_DOMAINS = [
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "wikipedia.org",
    "crunchbase.com",
    "glassdoor.com",
    "indeed.com",
    "bloomberg.com",
    "youtube.com",
    "google.com",
    "maps.google.com",
    "reddit.com",
    "fandom.com",
    "hoyoverse.com",
]


def is_blocked_domain(domain: str) -> bool:
    domain = domain.lower()

    for blocked_domain in BLOCKED_DOMAINS:
        if domain == blocked_domain or domain.endswith("." + blocked_domain):
            return True

    return False