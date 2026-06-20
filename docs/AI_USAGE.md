# AI Tooling Usage Report

The MDS lab requires AI tools to be used across **all** phases of development.
This report documents where and how AI was used to build Finalytics.

## Summary

| Phase | AI tool usage | Outcome |
|-------|---------------|---------|
| Backlog & user stories | LLM-assisted drafting of the 15 user stories and 5 epics in the Trello backlog | `ecgBGkcl - finalytics-backlog.json` |
| Architecture & diagrams | LLM used to design the microservice split and generate Mermaid diagrams | `docs/architecture.md` |
| Implementation | AI coding assistant generated the AI module, scoring engine, backend feature endpoints, and frontend integration | `ai_module/`, `backend/`, `frontend/` |
| In-product AI | 2 functional AI agents (Risk Analyst, Sales Strategist) + a Q&A agent powered by OpenAI | `ai_module/app/agents/` |
| Testing & evals | AI generated unit tests, API integration tests, and agent eval harness | `ai_module/tests/`, `backend/tests/` |
| Debugging | AI assistant identified and fixed the intent-detection bug (TVA acronym) | PR `fix/intent-detection-tva` |
| CI/CD | AI generated the GitHub Actions pipeline | `.github/workflows/ci.yml` |
| Documentation | AI drafted the README, architecture docs, and this report | `README.md`, `docs/` |

## In-product AI agents (graded feature — 3 pts)

Finalytics ships **two AI agents that are part of the product functionality**
(not code-writing assistants):

1. **Risk Analyst Agent** (`ai_module/app/agents/risk_analyst.py`, US13)
   Interprets ANAF + Monitorul Oficial + BPI data and the computed score, then
   explains the collaboration risk in natural Romanian.

2. **Sales Strategist Agent** (`ai_module/app/agents/sales_strategist.py`, US14)
   Produces concrete commercial recommendations (payment terms, safeguards,
   outreach angle) adapted to the company's risk band.

A third **Q&A agent** (US9) answers free-form questions about a company.

### Grounding & anti-hallucination

All agents receive a compact, factual context built from real data
(`ai_module/app/agents/context.py`) and are instructed to use only that
context. When the LLM is unavailable, deterministic fallbacks keep the product
working — important because the lab notes that small/local models may
hallucinate. The model is configurable via `OPENAI_MODEL` and can point at a
local OpenAI-compatible endpoint.

### Agent evals

`ai_module/tests/test_agents.py` contains the eval harness. It asserts that:
- the Risk Analyst's output is grounded in the actual risk (e.g. mentions
  bankruptcy for a bankrupt company),
- the Sales Strategist adapts recommendations to the risk band (advance payment
  for high risk vs. standard terms for healthy),
- outputs differ meaningfully between a healthy and a risky company.

## How to reproduce

The AI agents run live with a real key; CI runs them on the deterministic
fallback path (no key needed) so the build is hermetic and free.
