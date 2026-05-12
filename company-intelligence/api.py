from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from company_intelligence import aggregate_company_data


app = FastAPI(
    title="Company Intelligence API",
    version="1.0.0",
    description="Monitorul Oficial + ONRC BPI intelligence API"
)


@app.get("/")
def root():

    return {
        "service": "company-intelligence-api",
        "status": "running"
    }


@app.get("/health")
def health():

    return {
        "status": "healthy"
    }


@app.get("/company/{cui}")
def get_company(cui: str):

    try:

        data = aggregate_company_data(cui)

        return JSONResponse(content=data)

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )