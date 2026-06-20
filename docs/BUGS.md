# Bug Tracking

Bugs are reported here and fixed via dedicated `fix/*` branches merged through
pull requests.

---

## BUG-001 — Follow-up questions misclassified as a new analysis

- **Status:** Fixed (PR `fix/intent-detection-tva`)
- **Severity:** High (charges tokens and blocks the Q&A feature)
- **Reported during:** end-to-end browser smoke test of the chat UI

### Steps to reproduce
1. Log in and analyze a company (e.g. `analizeaza CUI 14388248`).
2. Ask a natural follow-up question: `Este firma platitoare de TVA si de cat timp exista?`

### Expected
The message is treated as a **question** about the already-analyzed company and
routed to the Q&A agent (`POST /api/ai/ask`).

### Actual
The message was treated as a **new analysis request** and failed with
`Eroare: Insufficient tokens. Need 7, have 3`.

### Root cause
`parseMessage()` detects a company name with an all-caps regex. Common Romanian
acronyms such as **TVA**, **CUI**, **SRL**, **ANAF**, **BPI** match that
pattern, so the word "TVA" in the question was extracted as a company name and
the intent became `analyze` instead of `unknown`/question.

### Fix
- Maintain a stopword set of domain acronyms that must not be treated as company
  names.
- Treat a message as a question (Q&A) when a company context already exists and
  the message looks like a question (ends with `?` or starts with a question
  word) and contains no CUI.

See PR `fix/intent-detection-tva` for the change and the regression test.
