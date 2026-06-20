"""
ANAF API Proxy - Full company info (TVA, e-Factura status, addresses, etc.)
Uses the official V9 endpoint: https://webservicesp.anaf.ro/api/PlatitorTvaRest/v9/tva
"""
import requests
from datetime import date
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI(
    title="ANAF Proxy API",
    description="Proxy for ANAF company verification (TVA, e-Factura, status)",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ANAF_URL = "https://webservicesp.anaf.ro/api/PlatitorTvaRest/v9/tva"


class AnafRequest(BaseModel):
    cui: int
    data: Optional[str] = None  # yyyy-MM-dd, defaults to today


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/efactura")
def query_anaf(req: AnafRequest):
    """
    Query ANAF V9 endpoint for full company info.
    Returns: date_generale, TVA status, e-Factura status, addresses, etc.
    """
    query_date = req.data or date.today().isoformat()

    payload = [{"cui": req.cui, "data": query_date}]

    try:
        response = requests.post(
            ANAF_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()

            # Transform to a cleaner response for the frontend
            if data.get("found") and len(data["found"]) > 0:
                company = data["found"][0]
                dg = company.get("date_generale", {})
                tva = company.get("inregistrare_scop_Tva", {})
                rtvai = company.get("inregistrare_RTVAI", {})
                stare = company.get("stare_inactiv", {})
                sediu = company.get("adresa_sediu_social", {})
                fiscal = company.get("adresa_domiciliu_fiscal", {})

                return {
                    "found": [{
                        "cui": dg.get("cui"),
                        "denumire": dg.get("denumire"),
                        "adresa": dg.get("adresa"),
                        "telefon": dg.get("telefon"),
                        "fax": dg.get("fax"),
                        "codPostal": dg.get("codPostal"),
                        "nrRegCom": dg.get("nrRegCom"),
                        "cod_CAEN": dg.get("cod_CAEN"),
                        "stare_inregistrare": dg.get("stare_inregistrare"),
                        "data_inregistrare": dg.get("data_inregistrare"),
                        "statusRO_e_Factura": dg.get("statusRO_e_Factura"),
                        "data_inreg_Reg_RO_e_Factura": dg.get("data_inreg_Reg_RO_e_Factura"),
                        "organFiscalCompetent": dg.get("organFiscalCompetent"),
                        "forma_de_proprietate": dg.get("forma_de_proprietate"),
                        "forma_organizare": dg.get("forma_organizare"),
                        "forma_juridica": dg.get("forma_juridica"),
                        "iban": dg.get("iban"),
                        "tva": {
                            "platitorTVA": tva.get("scpTVA"),
                            "perioade": tva.get("perioade_TVA", []),
                        },
                        "tva_incasare": {
                            "status": rtvai.get("statusTvaIncasare"),
                            "dataInceput": rtvai.get("dataInceputTvaInc"),
                            "dataSfarsit": rtvai.get("dataSfarsitTvaInc"),
                        },
                        "stare_inactiv": {
                            "statusInactivi": stare.get("statusInactivi"),
                            "dataInactivare": stare.get("dataInactivare"),
                            "dataReactivare": stare.get("dataReactivare"),
                            "dataRadiere": stare.get("dataRadiere"),
                        },
                        "adresa_sediu": {
                            "strada": sediu.get("sdenumire_Strada"),
                            "numar": sediu.get("snumar_Strada"),
                            "localitate": sediu.get("sdenumire_Localitate"),
                            "judet": sediu.get("sdenumire_Judet"),
                            "cod_postal": sediu.get("scod_Postal"),
                        },
                        "adresa_fiscal": {
                            "strada": fiscal.get("ddenumire_Strada"),
                            "numar": fiscal.get("dnumar_Strada"),
                            "localitate": fiscal.get("ddenumire_Localitate"),
                            "judet": fiscal.get("ddenumire_Judet"),
                            "cod_postal": fiscal.get("dcod_Postal"),
                        },
                    }],
                    "notFound": []
                }
            else:
                return {"found": [], "notFound": [req.cui]}

        elif response.status_code == 404:
            return {"found": [], "notFound": [req.cui]}
        else:
            return {
                "found": [],
                "notFound": [req.cui],
                "error": f"ANAF returned status {response.status_code}"
            }

    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="ANAF service timeout")
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=502, detail="Cannot connect to ANAF service")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
