"""
Finalytics Backend - Auth, RBAC, Token Economy, Unified Analysis API.
"""
import os
import json
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import jwt, JWTError
from passlib.context import CryptContext


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

# ─── Storage (JSON file-based for MVP) ────────────────────────────────────────

DATA_DIR = Path("/app/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
USERS_FILE = DATA_DIR / "users.json"
LOGS_FILE = DATA_DIR / "analysis_logs.json"


def load_users():
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text())
    return {}


def save_users(users):
    USERS_FILE.write_text(json.dumps(users, indent=2, default=str))


def load_logs():
    if LOGS_FILE.exists():
        return json.loads(LOGS_FILE.read_text())
    return []


def save_log_entry(entry):
    logs = load_logs()
    logs.append(entry)
    # Keep last 1000 entries
    if len(logs) > 1000:
        logs = logs[-1000:]
    LOGS_FILE.write_text(json.dumps(logs, indent=2, default=str))


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


def create_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
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
            "created_at": datetime.utcnow().isoformat(),
        }
    if "demo" not in users:
        users["demo"] = {
            "username": "demo",
            "password_hash": pwd_context.hash("demo123"),
            "email": "demo@finalytics.ro",
            "role": "user",
            "tokens": 50,
            "created_at": datetime.utcnow().isoformat(),
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
        "created_at": datetime.utcnow().isoformat(),
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
        "timestamp": datetime.utcnow().isoformat(),
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
