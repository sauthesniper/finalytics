"""
Web Research Agent (agentic, ReAct-style) — US12 enrichment.

Unlike the deterministic single-shot website discovery, this agent runs a
reasoning loop with tools (OpenAI function-calling):

  - search_web(query)  -> raw Google results via the serp-api service
  - fetch_page(url)     -> downloads a page, extracts text, checks whether the
                           company name / CUI appear (verification)
  - finish(...)         -> returns the final website + a short web profile

It plans a query, inspects the results, reformulates (e.g. drops "SRL", adds
"Romania" or the city from the ANAF address), optionally opens a page to
confirm, and decides. Every step is streamed so the UI can show the agent
"actively searching". When no LLM is available it degrades to a deterministic
trace built from the aggregated SERP data, so the product always responds.
"""
import json
import os
import re
from typing import Dict, Any, List, Iterator, Optional

import requests

from app.llm import chat_with_tools, llm_available, MODEL

SERP_URL = os.getenv("SERP_URL", "http://serp-api:3000")
SERP_API_KEY = os.getenv("SERP_API_KEY", "dev-secret-key")
SERP_TIMEOUT = int(os.getenv("SERP_TIMEOUT", "30"))
FETCH_TIMEOUT = int(os.getenv("FETCH_TIMEOUT", "12"))
MAX_STEPS = int(os.getenv("WEB_RESEARCH_MAX_STEPS", "4"))
MAX_PAGE_CHARS = 3000

SYSTEM_PROMPT = (
    "Ești un agent de cercetare web pentru firme din România. Scopul tău este să "
    "găsești (1) CODUL FISCAL / CUI al firmei și (2) website-ul OFICIAL + un scurt profil. "
    "Ai la dispoziție unelte: search_web(query), fetch_page(url) și finish(...). "
    "Lucrează în pași: caută firma (ex. 'NUME firma CUI cod fiscal', sau pe agregatoare "
    "ca listafirme.ro / termene.ro / risco.ro / mfinante), deschide o pagină candidată cu "
    "fetch_page și extrage CUI-ul (cod numeric, de obicei 6-9 cifre) confirmând că numele "
    "firmei se potrivește. Reformulează interogarea dacă e nevoie (elimină 'SRL', adaugă "
    "'Romania' sau orașul). Apoi cheamă finish cu cui (doar cifrele), website, încredere 0-1 "
    "și un rezumat scurt în limba română. Evită rețele sociale ca website oficial. "
    "Nu inventa — dacă nu găsești CUI-ul sau website-ul, lasă-le null în finish."
)

# ─── Tool definitions (OpenAI function-calling schema) ────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Caută pe Google și întoarce rezultate (titlu + url).",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "interogarea de căutare"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_page",
            "description": "Descarcă o pagină web și întoarce un fragment de text plus dacă numele/CUI-ul firmei apar pe ea.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Întoarce rezultatul final al cercetării.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cui": {"type": ["string", "null"], "description": "codul fiscal/CUI (doar cifrele)"},
                    "website": {"type": ["string", "null"]},
                    "confidence": {"type": "number"},
                    "summary": {"type": "string"},
                },
                "required": ["confidence", "summary"],
            },
        },
    },
]

_BLOCKED = ("linkedin.", "facebook.", "instagram.", "twitter.", "x.com",
            "wikipedia.", "youtube.", "google.")


def valid_cui(cui) -> bool:
    """Validate a Romanian CUI/CIF using the official control-digit checksum."""
    s = re.sub(r"\D", "", str(cui or ""))
    if not (2 <= len(s) <= 10):
        return False
    key = "753217532"
    body, check = s[:-1], int(s[-1])
    key = key[-len(body):]
    total = sum(int(d) * int(k) for d, k in zip(body, key))
    r = (total * 10) % 11
    if r == 10:
        r = 0
    return r == check


def _clean_cui(cui) -> str:
    return re.sub(r"\D", "", str(cui or ""))


# ─── Tools implementation ─────────────────────────────────────────────────────

def _tool_search_web(query: str) -> List[Dict[str, str]]:
    try:
        resp = requests.post(
            f"{SERP_URL}/search",
            json={"query": query, "num": 10},
            headers={"x-api-key": SERP_API_KEY},
            timeout=SERP_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("results", [])
    except requests.RequestException:
        return []


def _strip_html(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _tool_fetch_page(url: str, name: Optional[str], cui: Optional[str]) -> Dict[str, Any]:
    if not url or not url.lower().startswith(("http://", "https://")):
        return {"url": url, "ok": False, "verified": False, "text": "", "error": "url invalid"}
    try:
        resp = requests.get(url, timeout=FETCH_TIMEOUT,
                            headers={"User-Agent": "FinalyticsBot/1.0"})
        resp.raise_for_status()
        text = _strip_html(resp.text)[:MAX_PAGE_CHARS]
        haystack = text.lower()
        verified = False
        if name:
            tokens = [t for t in re.split(r"\s+", name.lower()) if len(t) > 2
                      and t not in ("srl", "sa", "pfa", "srl-d")]
            verified = any(t in haystack for t in tokens) if tokens else False
        if cui and str(cui) in haystack:
            verified = True
        return {"url": url, "ok": True, "verified": verified, "text": text}
    except requests.RequestException as exc:
        return {"url": url, "ok": False, "verified": False, "text": "", "error": str(exc)}


# ─── Deterministic fallback (no LLM) ──────────────────────────────────────────

def _serp_discover(name: Optional[str]) -> Optional[Dict[str, Any]]:
    """One-shot deterministic website discovery (used by the fallback path)."""
    if not name:
        return None
    try:
        resp = requests.post(
            f"{SERP_URL}/discover",
            json={"companyName": name},
            headers={"x-api-key": SERP_API_KEY},
            timeout=SERP_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return None


def _fallback_stream(bundle: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    name = bundle.get("company_name") or f"CUI {bundle.get('cui')}"
    cui = str(bundle.get("cui")) if bundle.get("cui") else None
    serp = bundle.get("serp") or _serp_discover(bundle.get("company_name")) or {}
    yield {"type": "thought", "text": "Model LLM indisponibil — folosesc căutarea deterministă."}
    yield {"type": "tool_call", "tool": "search_web", "query": f"{name} official website"}
    alts = serp.get("alternatives") or []
    yield {"type": "tool_result", "tool": "search_web", "n": len(alts),
           "top": [{"title": a.get("domain"), "url": a.get("url")} for a in alts[:3]]}
    if serp.get("status") == "found" and serp.get("website"):
        yield {"type": "answer", "cui": cui, "website": serp.get("website"),
               "confidence": serp.get("confidence", 0.0),
               "summary": f"Website probabil pentru {name}: {serp.get('website')}."}
    else:
        yield {"type": "answer", "cui": cui, "website": None, "confidence": 0.0,
               "summary": f"Nu am putut confirma un website oficial pentru {name}."}


# ─── Agentic loop (streaming) ─────────────────────────────────────────────────

def _initial_user_prompt(bundle: Dict[str, Any]) -> str:
    name = bundle.get("company_name") or "necunoscut"
    cui = bundle.get("cui") or "necunoscut"
    anaf = bundle.get("anaf") or {}
    address = anaf.get("adresa") or "necunoscută"
    caen = anaf.get("cod_CAEN") or "necunoscut"
    return (
        f"Găsește website-ul oficial al firmei.\n"
        f"NUME: {name}\nCUI: {cui}\nADRESĂ: {address}\nCOD CAEN: {caen}\n"
        "Începe printr-o căutare; reformulează dacă e nevoie; confirmă cu fetch_page; "
        "apoi cheamă finish."
    )


def run_web_research_stream(bundle: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    """Yield step events ('start','thought','tool_call','tool_result','answer','error')."""
    name = bundle.get("company_name")
    cui = bundle.get("cui")

    if not llm_available():
        yield {"type": "start", "used_llm": False, "model": "rule-based-fallback"}
        yield from _fallback_stream(bundle)
        return

    yield {"type": "start", "used_llm": True, "model": MODEL}

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _initial_user_prompt(bundle)},
    ]

    for _ in range(MAX_STEPS):
        msg, used = chat_with_tools(messages, TOOLS)
        if not used or msg is None:
            yield from _fallback_stream(bundle)
            return

        tool_calls = getattr(msg, "tool_calls", None) or []
        if msg.content:
            yield {"type": "thought", "text": msg.content}

        if not tool_calls:
            yield {"type": "answer", "cui": str(cui) if cui else None,
                   "website": None, "confidence": 0.0,
                   "summary": msg.content or "Cercetare finalizată."}
            return

        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in tool_calls
            ],
        })

        for tc in tool_calls:
            fname = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            if fname == "finish":
                raw_cui = args.get("cui")
                cui_out = _clean_cui(raw_cui) if raw_cui else None
                if cui_out and not valid_cui(cui_out):
                    cui_out = None  # reject implausible CUIs (phone numbers, etc.)
                yield {"type": "answer",
                       "cui": cui_out or (str(cui) if cui else None),
                       "website": args.get("website"),
                       "confidence": float(args.get("confidence") or 0.0),
                       "summary": args.get("summary") or ""}
                return

            if fname == "search_web":
                query = args.get("query", "")
                yield {"type": "tool_call", "tool": "search_web", "query": query}
                results = _tool_search_web(query)
                yield {"type": "tool_result", "tool": "search_web",
                       "n": len(results), "top": results[:3]}
                tool_content = json.dumps(results[:8], ensure_ascii=False)
            elif fname == "fetch_page":
                url = args.get("url", "")
                yield {"type": "tool_call", "tool": "fetch_page", "url": url}
                page = _tool_fetch_page(url, name, cui)
                yield {"type": "tool_result", "tool": "fetch_page",
                       "url": url, "verified": page.get("verified", False),
                       "ok": page.get("ok", False)}
                tool_content = json.dumps(
                    {"url": url, "verified": page.get("verified"),
                     "text": page.get("text", "")[:1500]}, ensure_ascii=False)
            else:
                tool_content = json.dumps({"error": f"unknown tool {fname}"})

            messages.append({"role": "tool", "tool_call_id": tc.id, "content": tool_content})

    yield {"type": "answer", "cui": str(cui) if cui else None,
           "website": None, "confidence": 0.0,
           "summary": "Nu am putut confirma un website oficial în pașii disponibili."}


def run_web_research(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """Non-streaming variant: runs the agent and returns the final result + trace."""
    steps: List[Dict[str, Any]] = []
    answer: Dict[str, Any] = {"cui": None, "website": None, "confidence": 0.0, "summary": ""}
    used_llm = llm_available()
    for ev in run_web_research_stream(bundle):
        if ev.get("type") == "answer":
            answer = {"cui": ev.get("cui"),
                      "website": ev.get("website"),
                      "confidence": ev.get("confidence", 0.0),
                      "summary": ev.get("summary", "")}
        else:
            steps.append(ev)
    return {
        "agent": "web_research",
        "cui": answer["cui"] or bundle.get("cui"),
        "company_name": bundle.get("company_name"),
        "website": answer["website"],
        "confidence": answer["confidence"],
        "summary": answer["summary"],
        "steps": steps,
        "used_llm": used_llm,
        "model": MODEL if used_llm else "rule-based-fallback",
    }
