"""
Finalytics Backend - Auth, RBAC, Token Economy, Unified Analysis API.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import jwt, JWTError
from passlib.context import CryptContext

import storage
import integrations
import reports


# ─── Config ───────────────────────────────────────────────────────────────────

SECRET_KEY = os.getenv("SECRET_KEY", "finalytics-secret-key-change-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24h

# Token costs per service
TOKEN_COSTS = {
    "serp": 2,
    "anaf": 1,
    "intel": 3,
    "berc": 5,
    "full_analysis": 10,
}

# ─── Storage (thread-safe JSON via storage module) ───────────────────────────

USERS_FILE = "users.json"
LOGS_FILE = "analysis_logs.json"
FEEDBACK_FILE = "feedback.json"
ALERTS_FILE = "alerts.json"
SNAPSHOTS_FILE = "snapshots.json"


def load_users():
    return storage.read_json(USERS_FILE, {})


def save_users(users):
    storage.write_json(USERS_FILE, users)


def load_logs():
    return storage.read_json(LOGS_FILE, [])


def save_log_entry(entry):
    def mutate(logs):
        logs.append(entry)
        if len(logs) > 1000:
            logs = logs[-1000:]
        return logs
    storage.update_json(LOGS_FILE, [], mutate)


def record_snapshot(cui, company_name, score, band):
    """Append a timestamped score snapshot for company history (US5)."""
    if not cui:
        return

    def mutate(snaps):
        bucket = snaps.setdefault(str(cui), [])
        bucket.append({
            "company_name": company_name,
            "score": score,
            "band": band,
            "timestamp": _now_iso(),
        })
        # keep last 100 snapshots per company
        snaps[str(cui)] = bucket[-100:]
        return snaps
    storage.update_json(SNAPSHOTS_FILE, {}, mutate)


# ─── Auth ─────────────────────────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

app = FastAPI(title="Finalytics API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _now_dt():
    return datetime.now(timezone.utc)


def _now_iso():
    return _now_dt().isoformat()


def create_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = _now_dt() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    users = load_users()
    username = payload.get("sub")
    if username not in users:
        raise HTTPException(status_code=401, detail="User not found")
    return users[username]


def require_role(role: str):
    def checker(user=Depends(get_current_user)):
        if user["role"] not in [role, "admin"]:
            raise HTTPException(status_code=403, detail=f"Requires role: {role}")
        return user
    return checker


# ─── Models ───────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenGrantRequest(BaseModel):
    username: str
    tokens: int


class AnalysisRequest(BaseModel):
    company_name: Optional[str] = None
    cui: Optional[str] = None
    services: list[str] = ["serp", "anaf", "intel", "berc"]


class FeedbackRequest(BaseModel):
    cui: str
    rating: int  # 1-5
    comment: Optional[str] = None


class TrackRequest(BaseModel):
    cui: str
    company_name: Optional[str] = None


class CompanyRef(BaseModel):
    cui: Optional[str] = None
    company_name: Optional[str] = None


class CompareRequest(BaseModel):
    companies: list[CompanyRef]


class ExportRequest(BaseModel):
    cui: Optional[str] = None
    company_name: Optional[str] = None
    format: str = "json"  # json | pdf


# ─── Init default admin ──────────────────────────────────────────────────────

def init_default_users():
    users = load_users()
    if "admin" not in users:
        users["admin"] = {
            "username": "admin",
            "password_hash": pwd_context.hash("admin123"),
            "email": "admin@finalytics.ro",
            "role": "admin",
            "tokens": 9999,
            "created_at": _now_iso(),
        }
    if "demo" not in users:
        users["demo"] = {
            "username": "demo",
            "password_hash": pwd_context.hash("demo123"),
            "email": "demo@finalytics.ro",
            "role": "user",
            "tokens": 50,
            "created_at": _now_iso(),
        }
    save_users(users)


init_default_users()


# ─── Routes: Health ───────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "finalytics-backend"}


# ─── Routes: Auth ─────────────────────────────────────────────────────────────

@app.post("/auth/register")
def register(req: RegisterRequest):
    users = load_users()
    if req.username in users:
        raise HTTPException(status_code=400, detail="Username already exists")

    users[req.username] = {
        "username": req.username,
        "password_hash": pwd_context.hash(req.password),
        "email": req.email,
        "role": "user",
        "tokens": 10,  # Free starter tokens
        "created_at": _now_iso(),
    }
    save_users(users)

    token = create_token({"sub": req.username, "role": "user"})
    return {
        "message": "Account created",
        "token": token,
        "username": req.username,
        "tokens": 10,
        "role": "user",
    }


@app.post("/auth/login")
def login(req: LoginRequest):
    users = load_users()
    user = users.get(req.username)
    if not user or not pwd_context.verify(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token({"sub": req.username, "role": user["role"]})
    return {
        "token": token,
        "username": user["username"],
        "role": user["role"],
        "tokens": user["tokens"],
        "email": user.get("email"),
    }


@app.get("/auth/me")
def get_me(user=Depends(get_current_user)):
    return {
        "username": user["username"],
        "role": user["role"],
        "tokens": user["tokens"],
        "email": user.get("email"),
        "created_at": user.get("created_at"),
    }


# ─── Routes: Admin ───────────────────────────────────────────────────────────

@app.post("/admin/grant-tokens")
def grant_tokens(req: TokenGrantRequest, user=Depends(require_role("admin"))):
    users = load_users()
    if req.username not in users:
        raise HTTPException(status_code=404, detail="User not found")

    users[req.username]["tokens"] += req.tokens
    save_users(users)

    return {
        "message": f"Granted {req.tokens} tokens to {req.username}",
        "new_balance": users[req.username]["tokens"],
    }


@app.get("/admin/users")
def list_users(user=Depends(require_role("admin"))):
    users = load_users()
    return [
        {
            "username": u["username"],
            "role": u["role"],
            "tokens": u["tokens"],
            "email": u.get("email"),
            "created_at": u.get("created_at"),
        }
        for u in users.values()
    ]


@app.get("/admin/logs")
def get_logs(user=Depends(require_role("admin"))):
    return load_logs()[-50:]


@app.get("/admin/token-costs")
def get_token_costs(user=Depends(require_role("admin"))):
    return TOKEN_COSTS


# ─── Routes: Token Info ───────────────────────────────────────────────────────

@app.get("/tokens/balance")
def get_balance(user=Depends(get_current_user)):
    return {"tokens": user["tokens"], "username": user["username"]}


@app.get("/tokens/costs")
def get_costs():
    return TOKEN_COSTS


# ─── Routes: Analysis ─────────────────────────────────────────────────────────

@app.post("/analyze")
def run_analysis(req: AnalysisRequest, user=Depends(get_current_user)):
    """
    Deduct tokens and return a signed analysis ticket.
    The frontend uses this ticket to call individual services.
    """
    if not req.company_name and not req.cui:
        raise HTTPException(status_code=400, detail="Provide company_name or cui")

    # Calculate cost
    total_cost = sum(TOKEN_COSTS.get(s, 0) for s in req.services)

    if user["tokens"] < total_cost:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient tokens. Need {total_cost}, have {user['tokens']}"
        )

    # Deduct tokens
    users = load_users()
    users[user["username"]]["tokens"] -= total_cost
    save_users(users)

    # Create analysis ticket
    ticket_id = str(uuid.uuid4())[:8]
    ticket = create_token({
        "sub": user["username"],
        "ticket": ticket_id,
        "services": req.services,
        "company_name": req.company_name,
        "cui": req.cui,
        "cost": total_cost,
    }, expires_delta=timedelta(minutes=5))

    # Log
    save_log_entry({
        "ticket_id": ticket_id,
        "username": user["username"],
        "company_name": req.company_name,
        "cui": req.cui,
        "services": req.services,
        "cost": total_cost,
        "remaining_tokens": users[user["username"]]["tokens"],
        "timestamp": _now_iso(),
    })

    return {
        "ticket": ticket,
        "ticket_id": ticket_id,
        "services": req.services,
        "cost": total_cost,
        "remaining_tokens": users[user["username"]]["tokens"],
    }


@app.post("/analyze/validate-ticket")
def validate_ticket(ticket: str = Header(..., alias="x-analysis-ticket")):
    """Validate an analysis ticket (used by frontend before calling services)."""
    payload = verify_token(ticket)
    if not payload or "ticket" not in payload:
        raise HTTPException(status_code=401, detail="Invalid analysis ticket")
    return {
        "valid": True,
        "services": payload["services"],
        "company_name": payload.get("company_name"),
        "cui": payload.get("cui"),
    }


# ─── Routes: Feedback (US10) ──────────────────────────────────────────────────

@app.post("/feedback")
def add_feedback(req: FeedbackRequest, user=Depends(get_current_user)):
    """Add user feedback about a collaboration experience."""
    if req.rating < 1 or req.rating > 5:
        raise HTTPException(status_code=400, detail="rating must be 1-5")

    entry = {
        "id": str(uuid.uuid4())[:8],
        "username": user["username"],
        "rating": req.rating,
        "comment": req.comment,
        "created_at": _now_iso(),
    }

    def mutate(fb):
        fb.setdefault(req.cui, []).append(entry)
        return fb
    storage.update_json(FEEDBACK_FILE, {}, mutate)

    return {"message": "Feedback saved", "feedback": entry}


@app.get("/feedback/{cui}")
def get_feedback(cui: str):
    """Public list of feedback for a company, with an average rating."""
    fb = storage.read_json(FEEDBACK_FILE, {})
    items = fb.get(cui, [])
    avg = round(sum(i["rating"] for i in items) / len(items), 2) if items else None
    return {"cui": cui, "count": len(items), "average_rating": avg, "items": items}


# ─── Routes: Alerts (US6) ─────────────────────────────────────────────────────

@app.post("/alerts/track")
def track_company(req: TrackRequest, user=Depends(get_current_user)):
    """Track a company; stores a baseline score to detect future changes."""
    score = integrations.get_score(req.cui, req.company_name)
    baseline = score.get("score") if score else None
    band = score.get("band") if score else None

    entry = {
        "cui": req.cui,
        "company_name": req.company_name or (score.get("company_name") if score else None),
        "baseline_score": baseline,
        "baseline_band": band,
        "last_score": baseline,
        "last_band": band,
        "created_at": _now_iso(),
    }

    def mutate(alerts):
        user_alerts = alerts.setdefault(user["username"], [])
        # de-dup by cui
        user_alerts = [a for a in user_alerts if a["cui"] != req.cui]
        user_alerts.append(entry)
        alerts[user["username"]] = user_alerts
        return alerts
    storage.update_json(ALERTS_FILE, {}, mutate)

    if req.cui and baseline is not None:
        record_snapshot(req.cui, entry["company_name"], baseline, band)

    return {"message": "Company tracked", "tracked": entry}


@app.get("/alerts")
def list_alerts(user=Depends(get_current_user)):
    """List companies the user is tracking."""
    alerts = storage.read_json(ALERTS_FILE, {})
    return {"tracked": alerts.get(user["username"], [])}


@app.delete("/alerts/{cui}")
def untrack_company(cui: str, user=Depends(get_current_user)):
    def mutate(alerts):
        user_alerts = alerts.get(user["username"], [])
        alerts[user["username"]] = [a for a in user_alerts if a["cui"] != cui]
        return alerts
    storage.update_json(ALERTS_FILE, {}, mutate)
    return {"message": f"Stopped tracking {cui}"}


@app.post("/alerts/check")
def check_alerts(user=Depends(get_current_user)):
    """
    Re-score all tracked companies and report risk changes (US6).
    Updates baselines and records history snapshots.
    """
    alerts = storage.read_json(ALERTS_FILE, {})
    user_alerts = alerts.get(user["username"], [])
    changes = []

    for a in user_alerts:
        score = integrations.get_score(a["cui"], a.get("company_name"))
        if not score:
            continue
        new_score = score.get("score")
        new_band = score.get("band")
        prev = a.get("last_score")

        if prev is not None and new_score is not None and new_score != prev:
            changes.append({
                "cui": a["cui"],
                "company_name": a.get("company_name"),
                "previous_score": prev,
                "new_score": new_score,
                "previous_band": a.get("last_band"),
                "new_band": new_band,
                "direction": "improved" if new_score > prev else "worsened",
            })
        a["last_score"] = new_score
        a["last_band"] = new_band
        record_snapshot(a["cui"], a.get("company_name"), new_score, new_band)

    alerts[user["username"]] = user_alerts
    storage.write_json(ALERTS_FILE, alerts)

    return {"checked": len(user_alerts), "changes": changes}


# ─── Routes: History (US5) ────────────────────────────────────────────────────

@app.get("/history/{cui}")
def get_history(cui: str):
    """Timestamped score snapshots over time for a company."""
    snaps = storage.read_json(SNAPSHOTS_FILE, {})
    return {"cui": cui, "snapshots": snaps.get(str(cui), [])}


# ─── Routes: Compare (US7) ────────────────────────────────────────────────────

@app.post("/compare")
def compare_companies(req: CompareRequest, user=Depends(get_current_user)):
    """Compare 2+ companies via the AI module."""
    if len(req.companies) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 companies")
    payload = [{"cui": c.cui, "company_name": c.company_name} for c in req.companies]
    result = integrations.get_compare(payload)
    if result is None:
        raise HTTPException(status_code=503, detail="AI module unavailable")
    return result


# ─── Routes: Export (US11) ────────────────────────────────────────────────────

@app.post("/export")
def export_report(req: ExportRequest, user=Depends(get_current_user)):
    """Export a full company report as JSON or PDF (US11)."""
    if not req.cui and not req.company_name:
        raise HTTPException(status_code=400, detail="Provide cui or company_name")

    analysis = integrations.get_full_analysis(req.cui, req.company_name)
    if analysis is None:
        raise HTTPException(status_code=503, detail="AI module unavailable")

    score = analysis.get("score") or {}
    record_snapshot(req.cui, score.get("company_name") or req.company_name,
                    score.get("score"), score.get("band"))

    report = reports.build_report_data(req.cui, req.company_name, analysis)

    if req.format == "pdf":
        pdf_bytes = reports.build_report_pdf(report)
        filename = f"finalytics_{req.cui or 'report'}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return report

