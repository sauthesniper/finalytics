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
import json

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

load_dotenv()

from app.schemas import (
    ScoreRequest, ScoreResponse,
    AgentRequest, AgentResponse,
    AskRequest, AskResponse,
    CompareRequest, CompareResponse, CompareItem,
)
from app.aggregator import aggregate, aggregate_light
from app.scoring import compute_score
from app.agents import risk_analyst, sales_strategist, qa_agent
from app.agents.risk_analyst import run_risk_analyst
from app.agents.sales_strategist import run_sales_strategist
from app.agents.qa_agent import run_qa
from app.agents.web_research import run_web_research, run_web_research_stream
from app.llm import llm_available, stream_chat, MODEL

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


def _attach_documents(bundle, req) -> None:
    """Attach user-provided documents to the bundle so build_context includes them."""
    docs = getattr(req, "documents", None) or []
    if docs:
        bundle["user_documents"] = [
            {"name": d.name, "content": d.content} for d in docs
        ]


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
    _attach_documents(bundle, req)
    sc = compute_score(bundle)
    return run_risk_analyst(bundle, sc)


@app.post("/agent/sales", response_model=AgentResponse)
def agent_sales(req: AgentRequest):
    _require_ref(req)
    bundle = aggregate(req.cui, req.company_name)
    _attach_documents(bundle, req)
    sc = compute_score(bundle)
    return run_sales_strategist(bundle, sc)


@app.post("/agent/web-research")
def agent_web_research(req: AgentRequest):
    """Agentic web research: actively searches the web for the company (US12)."""
    _require_ref(req)
    bundle = aggregate_light(req.cui, req.company_name)
    return run_web_research(bundle)


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    _require_ref(req)
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="question is required")
    bundle = aggregate(req.cui, req.company_name)
    _attach_documents(bundle, req)
    sc = compute_score(bundle)
    return run_qa(bundle, sc, req.question.strip())


@app.post("/analyze")
def analyze(req: ScoreRequest):
    """Score + Risk Analyst + Sales Strategist in a single round trip."""
    _require_ref(req)
    bundle = aggregate(req.cui, req.company_name)
    _attach_documents(bundle, req)
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


# ─── Streaming (SSE) ──────────────────────────────────────────────────────────

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    # Tell nginx (both proxy layers) not to buffer, so tokens stream live.
    "X-Accel-Buffering": "no",
}


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _stream_text(system_prompt: str, user_prompt: str, fallback: str,
                 temperature: float = 0.3):
    """Yield text deltas from the LLM, or word-chunk the fallback if unavailable."""
    produced = False
    if llm_available():
        for delta in stream_chat(system_prompt, user_prompt, temperature=temperature):
            produced = True
            yield delta
    if not produced:
        # Stream the deterministic fallback word-by-word for a consistent UX.
        for word in fallback.split(" "):
            yield word + " "


@app.post("/analyze/stream")
def analyze_stream(req: ScoreRequest):
    """
    Stream a full analysis as Server-Sent Events:
      event: status  -> {"msg"}
      event: score   -> full score object (US3/US4)
      event: risk_start/risk_delta/risk_end    -> Risk Analyst (US13)
      event: sales_start/sales_delta/sales_end -> Sales Strategist (US14)
      event: done
    """
    _require_ref(req)

    def gen():
        yield _sse("status", {"msg": "aggregating"})
        bundle = aggregate(req.cui, req.company_name)
        _attach_documents(bundle, req)
        sc = compute_score(bundle)
        yield _sse("score", sc)

        used = llm_available()
        model = MODEL if used else "rule-based-fallback"

        # Risk Analyst
        yield _sse("risk_start", {"model": model, "used_llm": used})
        for delta in _stream_text(
            risk_analyst.SYSTEM_PROMPT,
            risk_analyst.build_user_prompt(bundle, sc),
            risk_analyst.fallback_text(bundle, sc),
            temperature=0.2,
        ):
            yield _sse("risk_delta", {"t": delta})
        yield _sse("risk_end", {})

        # Sales Strategist
        yield _sse("sales_start", {"model": model, "used_llm": used})
        for delta in _stream_text(
            sales_strategist.SYSTEM_PROMPT,
            sales_strategist.build_user_prompt(bundle, sc),
            sales_strategist.fallback_text(bundle, sc),
            temperature=0.4,
        ):
            yield _sse("sales_delta", {"t": delta})
        yield _sse("sales_end", {})

        yield _sse("done", {})

    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)


@app.post("/agent/web-research/stream")
def agent_web_research_stream(req: AgentRequest):
    """Stream the agentic web-research loop step-by-step (SSE)."""
    _require_ref(req)

    def gen():
        yield _sse("status", {"msg": "aggregating"})
        bundle = aggregate_light(req.cui, req.company_name)
        for step in run_web_research_stream(bundle):
            yield _sse(step.get("type", "step"), step)
        yield _sse("done", {})

    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)


@app.post("/ask/stream")
def ask_stream(req: AskRequest):
    """Stream a Q&A answer token-by-token (US9)."""
    _require_ref(req)
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="question is required")

    def gen():
        yield _sse("status", {"msg": "thinking"})
        bundle = aggregate(req.cui, req.company_name)
        _attach_documents(bundle, req)
        sc = compute_score(bundle)
        used = llm_available()
        yield _sse("start", {"model": MODEL if used else "rule-based-fallback", "used_llm": used})
        for delta in _stream_text(
            qa_agent.SYSTEM_PROMPT,
            qa_agent.build_user_prompt(bundle, sc, req.question.strip()),
            qa_agent.fallback_text(bundle, sc),
            temperature=0.2,
        ):
            yield _sse("delta", {"t": delta})
        yield _sse("done", {})

    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)
