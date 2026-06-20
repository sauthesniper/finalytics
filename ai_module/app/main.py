"""
Finalytics AI Module — scoring, explainability and AI agents.

Endpoints:
  GET  /health                health check
  POST /score                 Collaboration Health Score (US3, US4)
  POST /agent/risk            Risk Analyst Agent (US13)
  POST /agent/sales           Sales Strategist Agent (US14, US8)
  POST /ask                   Q&A about a company (US9)
  POST /compare               Compare 2+ companies (US7)
  POST /analyze               Score + both agents in one call
"""
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from app.schemas import (
    ScoreRequest, ScoreResponse,
    AgentRequest, AgentResponse,
    AskRequest, AskResponse,
    CompareRequest, CompareResponse, CompareItem,
)
from app.aggregator import aggregate
from app.scoring import compute_score
from app.agents.risk_analyst import run_risk_analyst
from app.agents.sales_strategist import run_sales_strategist
from app.agents.qa_agent import run_qa
from app.llm import llm_available, MODEL

app = FastAPI(title="Finalytics AI Module", version="1.0.0")

# CORS is intentionally permissive only for same-stack frontend use.
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _require_ref(req) -> None:
    if not req.cui and not req.company_name:
        raise HTTPException(status_code=400, detail="Provide cui or company_name")


@app.get("/health")
def health():
    return {"status": "ok", "service": "ai-module", "llm": llm_available(), "model": MODEL}


@app.post("/score", response_model=ScoreResponse)
def score(req: ScoreRequest):
    _require_ref(req)
    bundle = aggregate(req.cui, req.company_name)
    return compute_score(bundle)


@app.post("/agent/risk", response_model=AgentResponse)
def agent_risk(req: AgentRequest):
    _require_ref(req)
    bundle = aggregate(req.cui, req.company_name)
    sc = compute_score(bundle)
    return run_risk_analyst(bundle, sc)


@app.post("/agent/sales", response_model=AgentResponse)
def agent_sales(req: AgentRequest):
    _require_ref(req)
    bundle = aggregate(req.cui, req.company_name)
    sc = compute_score(bundle)
    return run_sales_strategist(bundle, sc)


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    _require_ref(req)
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="question is required")
    bundle = aggregate(req.cui, req.company_name)
    sc = compute_score(bundle)
    return run_qa(bundle, sc, req.question.strip())


@app.post("/analyze")
def analyze(req: ScoreRequest):
    """Score + Risk Analyst + Sales Strategist in a single round trip."""
    _require_ref(req)
    bundle = aggregate(req.cui, req.company_name)
    sc = compute_score(bundle)
    return {
        "score": sc,
        "risk_analyst": run_risk_analyst(bundle, sc),
        "sales_strategist": run_sales_strategist(bundle, sc),
    }


@app.post("/compare", response_model=CompareResponse)
def compare(req: CompareRequest):
    if len(req.companies) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 companies")

    items = []
    for c in req.companies:
        if not c.cui and not c.company_name:
            continue
        bundle = aggregate(c.cui, c.company_name)
        sc = compute_score(bundle)
        items.append(CompareItem(
            cui=sc.get("cui"),
            company_name=sc.get("company_name"),
            score=sc["score"],
            band=sc["band"],
            positives=sc.get("positives", [])[:3],
            negatives=sc.get("negatives", [])[:3],
        ))

    if not items:
        raise HTTPException(status_code=400, detail="No valid companies to compare")

    items.sort(key=lambda x: x.score, reverse=True)
    ranking = [i.company_name or i.cui or "necunoscut" for i in items]
    best = items[0]
    recommendation = (
        f"Cea mai sigură opțiune de colaborare este {best.company_name or best.cui} "
        f"cu scorul {best.score}/100 ({best.band})."
    )
    return CompareResponse(items=items, ranking=ranking, recommendation=recommendation)
