import re


def normalize_cui(cui: str) -> str:

    cui = (cui or "").strip().upper()

    cui = cui.replace("RO", "")

    cui = re.sub(r"\D+", "", cui)

    if not cui:
        raise ValueError("CUI invalid")

    return cui