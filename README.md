# 🚀 Finalytics

**Know before you trust. Decide before you risk.**

Finalytics este o aplicație de business intelligence pentru companii din România care adună date fragmentate, le transformă în insight-uri clare și răspunde la întrebarea care chiar contează:

> „Merită să colaborez cu firma asta?”

---

## 🧠 Ce face, pe scurt

Finalytics nu este doar un agregator de date. Este un motor de decizie care:

- 🔎 colectează date din multiple surse (publice + comerciale)
- 🧹 le normalizează și le corelează
- 📊 calculează un scor de risc / încredere
- 💡 explică scorul (fără magie neagră)
- 🎯 oferă recomandări concrete de colaborare

---

## ❗ Problema

Datele despre firme sunt peste tot… și nicăieri:

- ANAF pentru status fiscal  
- ONRC pentru date juridice  
- data.gov.ro pentru open data  
- alte surse pentru contracte, reputație, etc  

👉 Nimeni nu le leagă într-un mod util pentru decizii reale.

---

## ✅ Soluția

Finalytics creează un profil unic de companie, combinând toate aceste surse și transformându-le într-un **„health score” de colaborare** + insight-uri acționabile.

---

## 📊 Ce vede utilizatorul

### 🏢 Company Profile

Un „dosar inteligent” al firmei:

- date juridice și fiscale  
- activitate și CAEN  
- vechime și stabilitate  
- semnale de risc  
- prezență digitală  
- evoluție în timp  

---

### 📈 Collaboration Health Score (0–100)

| Scor   | Interpretare                  |
|--------|------------------------------|
| 80–100 | 🟢 colaborare confortabilă   |
| 60–79  | 🟡 ok, dar monitorizează     |
| 40–59  | 🟠 prudență                  |
| 0–39   | 🔴 risc ridicat              |

---

### 🔍 Explainability (fără cutii negre)

Pentru fiecare scor vezi:

- ✔️ ce a crescut scorul  
- ❌ ce l-a scăzut  
- ⚠️ ce date lipsesc  
- 🕒 cât de actuale sunt informațiile  

---

## 🧮 Cum calculăm scorul

Model bazat pe 6 piloni:

- Fiscal compliance  
- Stabilitate juridică  
- Sănătate financiară  
- Comportament comercial  
- Reputație operațională  
- Semnale de risc  

👉 fiecare pilon contribuie la scorul final (0–100)

---

## 🤖 AI Agents

Finalytics integrează 2 agenți AI funcționali în aplicație:

### 1. 🧠 Risk Analyst Agent

- interpretează datele brute  
- explică scorul în limbaj natural  
- răspunde la întrebări de tip:
  - „de ce e risky firma asta?”
  - „care e cel mai mare red flag?”

---

### 2. 🎯 Sales Strategist Agent

- oferă recomandări de abordare:
  - „cum să vinzi către firma asta?”
  - „ce tip de parteneriat e potrivit?”
- generează insight-uri de business (nu doar scoruri)

👉 rulează pe modele mici (posibil local), cu eval-uri incluse

---

## ⚙️ Funcționalități principale

- 🔎 Search companie după CUI / nume  
- 📊 Dashboard companie  
- 📈 Scor dinamic + explainability  
- 🔔 Alerts (schimbări, risc nou, status fiscal)  
- 🧠 AI insights (2 agenți)  
- 🧾 Integrare date publice (ANAF, ONRC, data.gov)  
- 🌐 Data enrichment (web presence, footprint)  
- 👤 User feedback (experiențe reale de colaborare)  
- 📁 Export raport (PDF / JSON)  
- 🔌 API pentru integrare externă  

---

## 🧪 User Stories (15) și unde sunt implementate

| # | User story | Status | Implementare |
|---|------------|--------|--------------|
| US1 | Caută firmă după CUI / nume | ✅ | `frontend` parser intent + `anaf-api` |
| US2 | Profil complet companie | ✅ | carduri ANAF / Intel / BERC în UI |
| US3 | Collaboration Health Score | ✅ | `ai_module/app/scoring.py` |
| US4 | Explicații pentru scor | ✅ | piloni + `reasons` în scoring |
| US5 | Istoricul firmei în timp | ✅ | `backend` snapshots + `GET /history/{cui}` |
| US6 | Alerte la schimbări de risc | ✅ | `backend` `/alerts/*` |
| US7 | Compară firme | ✅ | `ai-api /compare`, `backend /compare` |
| US8 | Recomandări de colaborare | ✅ | Sales Strategist Agent |
| US9 | Întreabă AI-ul despre firmă | ✅ | Q&A agent `ai-api /ask` |
| US10 | Feedback propriu | ✅ | `backend` `/feedback` |
| US11 | Export raport PDF/JSON | ✅ | `backend /export` (fpdf2) |
| US12 | Integrare date publice & enrichment | ✅ | `anaf-api`, `intel-api`, `serp-api` |
| US13 | Risk Analyst Agent | ✅ | `ai_module/app/agents/risk_analyst.py` |
| US14 | Sales Strategist Agent | ✅ | `ai_module/app/agents/sales_strategist.py` |
| US15 | API extern pentru integrare | ✅ | toate serviciile expun REST + OpenAPI `/docs` |

Backlog complet (Trello export): `ecgBGkcl - finalytics-backlog.json`

---

## 🧱 Arhitectură (as-built)

Finalytics este un set de microservicii **FastAPI** în spatele unui reverse
proxy **nginx**, plus un UI single-page. Fiecare modul are propria imagine
Docker și este orchestrat de `docker-compose.yml`.

| Serviciu | Port | Rol |
|----------|------|-----|
| `frontend` | 8080 | nginx + UI chat (HTML/CSS/JS) |
| `backend` | 8010 | auth, RBAC, token economy, feedback, alerts, history, export |
| `ai-api` | 8003 | scoring engine + 2 agenți AI + Q&A + compare |
| `anaf-api` | 8002 | proxy ANAF (TVA, e-Factura, stare fiscală) |
| `intel-api` | 8000 | Monitorul Oficial + ONRC BPI (insolvență) |
| `serp-api` | 3000 | descoperire website oficial |
| `berc-api` | 8001 | rapoarte ONRC BERC |

Diagrame complete (componente, secvență, scoring, agenți, workflow git):
👉 [`docs/architecture.md`](docs/architecture.md)

---

## ▶️ Cum rulezi

```bash
# 1. Configurează secretele
cp .env.example .env
#   completează OPENAI_API_KEY (pentru agenții AI) și restul cheilor

# 2. Pornește tot stackul
docker compose up --build

# 3. Deschide UI-ul
#    http://localhost:8080
#    cont demo: demo / demo123   |   admin: admin / admin123
```

Agenții AI rulează cu OpenAI dacă `OPENAI_API_KEY` e setat; altfel folosesc un
fallback determinist, astfel încât aplicația funcționează oricum. `OPENAI_MODEL`
poate fi îndreptat și către un model local compatibil OpenAI.

### Teste

```bash
cd ai_module && pip install -r requirements.txt pytest httpx && pytest   # scoring + agent evals
cd backend   && pip install -r requirements.txt pytest httpx && pytest   # auth + features
```

---

## 🔁 Dev Process (AI-driven) — livrabile MDS

| Cerință SOW (componenta B) | Unde se găsește |
|----------------------------|-----------------|
| User stories (min 10) + backlog | `ecgBGkcl - finalytics-backlog.json`, secțiunea User Stories de mai sus |
| Diagrame (componente, secvență, workflow) | [`docs/architecture.md`](docs/architecture.md) |
| Source control (branch, merge, PR, ≥5 commits/student) | istoric git: `feature/full-mvp-implementation`, `fix/intent-detection-tva` + Pull Requests |
| Teste automate + eval-uri agenți | `ai_module/tests/`, `backend/tests/` |
| Raportare bug + fix prin PR | [`docs/BUGS.md`](docs/BUGS.md) + PR `fix/intent-detection-tva` |
| Pipeline CI/CD | [`.github/workflows/ci.yml`](.github/workflows/ci.yml) |
| Raport folosire tooluri AI | [`docs/AI_USAGE.md`](docs/AI_USAGE.md) |

### 🤖 Cei 2 agenți AI (funcționalitate de produs)

- **Risk Analyst Agent** — explică riscul în limbaj natural (US13)
- **Sales Strategist Agent** — recomandări comerciale adaptate la risc (US14)

Ambii sunt grounded pe date reale și au eval-uri în `ai_module/tests/test_agents.py`.

