"""Same-origin API. Calculation/lookup is free; contribution is explicit."""
import hashlib
import hmac
import math
import mimetypes
import os
import secrets
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StrictBool, StrictInt
import db

mimetypes.add_type("text/javascript", ".mjs")
IS_PROD = db.is_production()
SECRET = os.environ.get("DEVICE_SECRET", "dev-only-change-me").encode()
if (IS_PROD or os.environ.get("DATABASE_URL")) and (
    len(SECRET) < 32 or SECRET.startswith(b"replace-")
):
    raise RuntimeError("Set DEVICE_SECRET to a random secret of at least 32 characters.")
if IS_PROD and not os.environ.get("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is required in production; refusing SQLite fallback.")
WEB_DIR = Path(os.environ.get("WEB_DIR", Path(__file__).resolve().parent.parent / "web" / "dist"))
MIN_COHORT = 20
MAX_PER_HOUR = int(os.environ.get("MAX_PER_HOUR", "60"))
RETENTION_DAYS = int(os.environ.get("RETENTION_DAYS", "90"))
if MAX_PER_HOUR < 1 or RETENTION_DAYS < 1:
    raise RuntimeError("MAX_PER_HOUR and RETENTION_DAYS must be positive.")
COOKIE = "skillissue_visitor"
COOKIE_AGE = 30 * 86400
app = FastAPI(title="skillissue.gg", docs_url=None, redoc_url=None, openapi_url=None)
origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if origins:
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True,
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


def sign(value):
    return hmac.new(SECRET, value.encode(), hashlib.sha256).hexdigest()


@app.middleware("http")
async def visitor_cookie(request: Request, call_next):
    if not request.url.path.startswith("/api/"):
        return await call_next(request)
    token = request.cookies.get(COOKIE, "")
    parts = token.split(".")
    valid = False
    if len(parts) == 3:
        ident, issued, signature = parts
        valid = (len(ident) == 32 and all(c in "0123456789abcdef" for c in ident)
                 and issued.isascii() and issued.isdigit() and len(issued) <= 12
                 and len(signature) == 64 and all(c in "0123456789abcdef" for c in signature)
                 and hmac.compare_digest(sign(f"{ident}.{issued}"), signature)
                 and 0 <= int(time.time()) - int(issued) < COOKIE_AGE)
    if not valid:
        value = f"{secrets.token_hex(16)}.{int(time.time())}"
        token = f"{value}.{sign(value)}"
    request.state.device = sign("device:" + token.split(".")[0])[:24]
    response = await call_next(request)
    if not valid:
        response.set_cookie(COOKIE, token, max_age=COOKIE_AGE, httponly=True,
                            secure=IS_PROD, samesite="lax", path="/")
    response.headers["Cache-Control"] = "no-store"
    return response


class Run(BaseModel):
    boss: str
    heals: StrictInt = Field(ge=0, le=999)
    revives: StrictInt = Field(ge=0, le=99)
    charmless: StrictBool
    bell: StrictBool
    prosthetic: StrictBool
    art: StrictBool
    cleared: StrictBool


def cohort_result(conn, boss, charmless, bell, score):
    # One statement gives count and rank from the same database snapshot.
    n, better = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(CASE WHEN score>? THEN 1 ELSE 0 END), 0) "
        "FROM submissions WHERE boss=? AND charmless=? AND bell=? AND excluded=0 AND ts>=?",
        (score, boss, int(charmless), int(bell), int(time.time()) - RETENTION_DAYS * 86400),
    ).fetchone()
    if n < MIN_COHORT:
        return {"status": "collecting", "n": n, "min_n": MIN_COHORT}
    # Competition rank: ties share a rank, rounded upward to a whole percent.
    top = min(100, max(1, math.ceil(100 * (better + 1) / n)))
    return {"status": "ok", "n": n, "top_percent": top,
            "basis": "submitted records on this site (self-reported, unverified)"}


@app.get("/healthz")
def healthz():
    conn = db.connect()
    try:
        conn.execute("SELECT 1").fetchone()
        return {"ok": True, "storage": "postgresql" if conn.pg else "sqlite"}
    finally:
        conn.close()


@app.get("/api/whoami")
def whoami(request: Request):
    return {"device": request.state.device[:6]}


@app.post("/api/submit")
def submit(run: Run, request: Request):
    run.boss = db.BOSS_ALIASES.get(run.boss, run.boss)
    if run.boss not in db.BOSSES or not run.cleared:
        raise HTTPException(422, "Choose a supported boss and confirm a completed victory.")
    dev, now = request.state.device, int(time.time())
    conn = db.connect()
    try:
        # Serialize duplicate/limit checks and insertion for this visitor.
        db.lock_submission(conn, dev)
        duplicate = conn.execute(
            "SELECT 1 FROM submissions WHERE device=? AND ts>? AND boss=? AND heals=? "
            "AND revives=? AND charmless=? AND bell=? AND prosthetic=? AND art=? LIMIT 1",
            (dev, now - 86400, run.boss, run.heals, run.revives, int(run.charmless),
             int(run.bell), int(run.prosthetic), int(run.art)),
        ).fetchone()
        if not duplicate:
            recent = conn.execute(
                "SELECT COUNT(*) FROM submissions WHERE device=? AND ts>?", (dev, now - 3600)
            ).fetchone()[0]
            if recent >= MAX_PER_HOUR:
                raise HTTPException(429, "Contribution limit reached. You can still calculate and compare records.")
            db.insert(conn, ts=now, device=dev, boss=run.boss, heals=run.heals,
                      revives=run.revives, charmless=run.charmless, bell=run.bell,
                      prosthetic=run.prosthetic, art=run.art)
        conn.commit()
        score = db.score_of(run.heals, run.revives)
        return {"score": score, "submission": "duplicate" if duplicate else "saved",
                "percentile": cohort_result(conn, run.boss, run.charmless, run.bell, score)}
    finally:
        conn.close()


@app.get("/api/percentile")
def percentile(boss: str, score: int, charmless: bool = False, bell: bool = False):
    boss = db.BOSS_ALIASES.get(boss, boss)
    if boss not in db.BOSSES or not 0 <= score <= 100:
        raise HTTPException(422, "Invalid query.")
    conn = db.connect()
    try:
        return cohort_result(conn, boss, charmless, bell, score)
    finally:
        conn.close()


if (WEB_DIR / "index.html").is_file():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
elif IS_PROD:
    raise RuntimeError("Frontend build is missing. Build web/ before starting production.")
