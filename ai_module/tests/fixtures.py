"""Shared fixture bundles representing aggregated company data."""

# A healthy, active, long-standing company with a website and no risk flags.
HEALTHY_BUNDLE = {
    "cui": "14388248",
    "company_name": "INTERNET TEAM SRL",
    "sources": ["anaf", "intel", "serp"],
    "anaf": {
        "denumire": "INTERNET TEAM SRL",
        "stare_inregistrare": "INREGISTRAT",
        "data_inregistrare": "2002-03-15",
        "statusRO_e_Factura": "Da",
        "cod_CAEN": "6201",
        "stare_inactiv": {"statusInactivi": False},
        "tva": {"platitorTVA": True},
    },
    "intel": {
        "monitorul_oficial": {"records": 2},
        "bpi": {"bulletins": []},
        "risk_flags": {
            "insolvency": False,
            "bankruptcy": False,
            "reorganization": False,
            "high_activity_company": False,
        },
        "meta": {"fetched_at": "2026-06-20T10:00:00+00:00"},
    },
    "serp": {
        "status": "found",
        "website": "https://internetteam.ro",
        "domain": "internetteam.ro",
        "confidence": 0.9,
    },
}

# A high-risk company: inactive, in bankruptcy, no website.
RISKY_BUNDLE = {
    "cui": "49068564",
    "company_name": "FIRMA RISCANTA SRL",
    "sources": ["anaf", "intel"],
    "anaf": {
        "denumire": "FIRMA RISCANTA SRL",
        "stare_inregistrare": "INREGISTRAT",
        "data_inregistrare": "2023-11-01",
        "statusRO_e_Factura": False,
        "cod_CAEN": "4321",
        "stare_inactiv": {"statusInactivi": True},
        "tva": {"platitorTVA": False},
    },
    "intel": {
        "monitorul_oficial": {"records": 12},
        "bpi": {"bulletins": [
            {"numar_buletin": "100", "an_buletin": "2025", "data_buletin": "2025-01-10",
             "text": "deschidere procedura faliment"},
        ]},
        "risk_flags": {
            "insolvency": True,
            "bankruptcy": True,
            "reorganization": False,
            "high_activity_company": True,
        },
        "meta": {"fetched_at": "2026-06-20T10:00:00+00:00"},
    },
    "serp": None,
}

# Sparse data: only ANAF responded.
SPARSE_BUNDLE = {
    "cui": "11111111",
    "company_name": None,
    "sources": ["anaf"],
    "anaf": {
        "denumire": "SPARSE SRL",
        "stare_inregistrare": "INREGISTRAT",
        "data_inregistrare": "2015-06-01",
        "statusRO_e_Factura": False,
        "stare_inactiv": {"statusInactivi": False},
        "tva": {"platitorTVA": True},
    },
    "intel": None,
    "serp": None,
}
