# Finalytics — Architecture & Diagrams

This document describes the **as-built** architecture of the Finalytics MVP.
All diagrams are written in Mermaid and render directly on GitHub.

## 1. Component / Container diagram

Finalytics is a set of FastAPI microservices behind an nginx reverse proxy,
plus a static single-page UI. Each module ships as its own Docker image and is
orchestrated by `docker-compose.yml`.

```mermaid
graph TD
    user([User / Browser])

    subgraph edge[Frontend container]
        nginx[nginx reverse proxy<br/>+ static SPA index.html]
    end

    subgraph core[Application services]
        backend[backend<br/>:8010<br/>auth, tokens, feedback,<br/>alerts, history, export]
        ai[ai-api<br/>:8003<br/>scoring + AI agents + Q&A]
    end

    subgraph data[Data services]
        anaf[anaf-api :8002<br/>ANAF fiscal proxy]
        intel[intel-api :8000<br/>Monitorul Oficial + BPI]
        serp[serp-api :3000<br/>website discovery]
        berc[berc-api :8001<br/>ONRC BERC reports]
    end

    ext1[(ANAF V9 API)]
    ext2[(SerpAPI)]
    ext3[(monitoruloficial.ro<br/>portal.onrc.ro)]
    openai[(OpenAI API)]

    user --> nginx
    nginx -->|/api/backend| backend
    nginx -->|/api/ai| ai
    nginx -->|/api/anaf| anaf
    nginx -->|/api/intel| intel
    nginx -->|/api/serp| serp
    nginx -->|/api/berc| berc

    backend -->|score / analyze / compare| ai
    ai --> anaf
    ai --> intel
    ai --> serp
    anaf --> ext1
    serp --> ext2
    intel --> ext3
    berc --> ext3
    ai -.LLM.-> openai
```

## 2. Analysis sequence (happy path)

How a single "analyze this company" request flows through the system.

```mermaid
sequenceDiagram
    actor U as User
    participant F as Frontend (nginx)
    participant B as backend
    participant AI as ai-api
    participant A as anaf-api
    participant I as intel-api
    participant S as serp-api
    participant O as OpenAI

    U->>F: "analizeaza CUI 14388248"
    F->>B: POST /analyze (ticket, deduct tokens)
    B-->>F: ticket + remaining tokens
    par Raw data cards
        F->>A: POST /efactura
        A-->>F: fiscal data
        F->>S: POST /discover
        S-->>F: website
    and AI score + agents
        F->>AI: POST /analyze {cui}
        AI->>A: fiscal data
        AI->>I: Monitorul Oficial + BPI
        AI->>S: website
        AI->>AI: compute Collaboration Health Score
        AI->>O: Risk Analyst prompt
        O-->>AI: risk narrative
        AI->>O: Sales Strategist prompt
        O-->>AI: recommendations
        AI-->>F: score + risk + sales
    end
    F-->>U: data cards + score + agent insights
```

## 3. Scoring model

The Collaboration Health Score (0–100) is a deterministic weighted sum of five
pillars. Each pillar produces a 0–100 sub-score and a list of human-readable
reasons (explainability).

```mermaid
graph LR
    LF[Legal & Fiscal<br/>weight 0.30]
    INS[Insolvency risk<br/>weight 0.30]
    TR[Transparency<br/>weight 0.15]
    ACT[Activity & age<br/>weight 0.15]
    FR[Data freshness<br/>weight 0.10]

    LF --> SUM((Weighted sum<br/>0-100))
    INS --> SUM
    TR --> SUM
    ACT --> SUM
    FR --> SUM

    SUM --> BAND{Band}
    BAND -->|>=70| H[healthy]
    BAND -->|40-69| C[caution]
    BAND -->|<40| R[high_risk]
```

## 4. AI agents

```mermaid
graph TD
    bundle[Aggregated company data<br/>+ Collaboration Score]
    ctx[Grounded context builder<br/>facts only, no invention]
    bundle --> ctx
    ctx --> risk[Risk Analyst Agent<br/>US13]
    ctx --> sales[Sales Strategist Agent<br/>US14]
    ctx --> qa[Q&A Agent<br/>US9]
    risk --> llm{OpenAI available?}
    sales --> llm
    qa --> llm
    llm -->|yes| out1[LLM narrative]
    llm -->|no| out2[Deterministic fallback]
```

The fallback path guarantees the agents always return a sensible, grounded
answer even with no API key or during an outage — and it is what the automated
agent evals exercise in CI.

## 5. Git / CI workflow

```mermaid
graph LR
    fb[feature/full-mvp-implementation] -->|PR| main
    bug[fix/intent-detection-tva] -->|PR| main
    main --> ci[GitHub Actions]
    ci --> t[pytest matrix<br/>ai_module + backend]
    ci --> l[ruff lint]
    ci --> d[docker build<br/>all modules]
```
