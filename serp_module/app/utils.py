from urllib.parse import urlparse


def extract_domain(url: str) -> str:
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.lower()

    if domain.startswith("www."):
        domain = domain[4:]

    return domain


def normalize_text(text: str) -> str:
    text = text.lower()
    text = text.replace(".", " ")
    text = text.replace(",", " ")
    text = text.replace("-", " ")
    text = text.replace("_", " ")
    text = text.replace("|", " ")

    return " ".join(text.split())


def company_name_tokens(company_name: str) -> list[str]:
    ignored_words = {
        "inc",
        "llc",
        "ltd",
        "limited",
        "corp",
        "corporation",
        "company",
        "companies",
        "co",
        "sa",
        "srl",
        "gmbh",
        "plc",
        "group",
        "holdings"
    }

    normalized_name = normalize_text(company_name)

    tokens = []

    for token in normalized_name.split():
        if token not in ignored_words:
            tokens.append(token)

    return tokens


def domain_without_tld(domain: str) -> str:
    parts = domain.lower().split(".")

    if len(parts) <= 1:
        return domain.lower()

    return parts[0]