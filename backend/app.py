"""skillissue.gg: serves the static site AND the API from one service.

Same origin, so no CORS setup is needed.

Local:   uvicorn app:app --port 8000          (SQLite file, dev secret)
Railway: DATABASE_URL + DEVICE_SECRET set as variables; see ../README.md
The ML pass (detect.py) runs separately as a cron service — never in the request path.
"""

import hashlib, hmac, mimetypes, os, sys, time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StrictBool, StrictInt

import db

mimetypes.add_type("text/javascript", ".mjs")  # ES modules must be served as JS

IS_PROD = bool(os.environ.get("DATABASE_URL") or os.environ.get("RAILWAY_ENVIRONMENT"))
SECRET = os.environ.get("DEVICE_SECRET", "dev-only-change-me").encode()
if IS_PROD and SECRET == b"dev-only-change-me":
    sys.exit("DEVICE_SECRET must be set in production (e.g. `openssl rand -hex 32`).")
WEB_DIR = Path(
    os.environ.get("WEB_DIR", Path(__file__).resolve().parent.parent / "web")
)
EXTRA_ORIGINS = [o for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o]
MIN_COHORT = 20  # below this, show "collecting data" instead of a percentile
MAX_PER_HOUR = int(os.environ.get("MAX_PER_HOUR", "10"))  # hard rate limit per device

app = FastAPI(title="skillissue.gg", docs_url=None, redoc_url=None, openapi_url=None)
if EXTRA_ORIGINS:  # only needed if the frontend is hosted on a different origin
    app.add_middleware(
        CORSMiddleware,
        allow_origins=EXTRA_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )


class Run(BaseModel):
    boss: str
    heals: StrictInt = Field(ge=0, le=999)
    revives: StrictInt = Field(ge=0, le=99)
    charmless: StrictBool
    bell: StrictBool
    prosthetic: StrictBool
    art: StrictBool
    cleared: StrictBool


def client_ip(request: Request) -> str:
    """Only trust forwarded headers behind a configured, verified reverse proxy."""
    if os.environ.get("TRUST_PROXY_HEADERS") != "1":
        return request.client.host if request.client else "?"
    h = request.headers
    return (
        h.get("x-real-ip")
        or h.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "?")
    )


def device_id(request: Request) -> str:
    """Pseudonymous device key.

    Hashed IPs are still personal data under GDPR, so disclose it.
    """
    ua = request.headers.get("user-agent", "")
    return hmac.new(
        SECRET, f"{client_ip(request)}|{ua}".encode(), hashlib.sha256
    ).hexdigest()[:24]


def cohort_result(conn, boss, charmless, bell, score):
    n = conn.execute(
        "SELECT COUNT(*) FROM submissions "
        "WHERE boss=? AND charmless=? AND bell=? AND excluded=0",
        (boss, int(charmless), int(bell)),
    ).fetchone()[0]
    if n < MIN_COHORT:
        return {"status": "collecting", "n": n, "min_n": MIN_COHORT}
    better = conn.execute(
        "SELECT COUNT(*) FROM submissions WHERE boss=? AND charmless=? AND bell=? "
        "AND excluded=0 AND score>?",
        (boss, int(charmless), int(bell), score),
    ).fetchone()[0]
    top = max(1, round(100 * (better + 1) / (n + 1)))  # ties share the same rank
    return {
        "status": "ok",
        "n": n,
        "top_percent": top,
        "basis": "submitted records on this site (self-reported, unverified)",
    }


@app.get("/healthz")
def healthz():
    conn = db.connect()
    try:
        conn.execute("SELECT 1").fetchone()
    finally:
        conn.close()
    return {"ok": True}


@app.get("/api/whoami")
def whoami(request: Request):
    """Deploy check: different networks/browsers should differ. Reveals no IP."""
    return {"device": device_id(request)[:6]}


@app.post("/api/submit")
def submit(run: Run, request: Request):
    run.boss = db.BOSS_ALIASES.get(run.boss, run.boss)
    if run.boss not in db.BOSSES:
        raise HTTPException(422, "Unsupported boss.")
    if not run.cleared:
        raise HTTPException(422, "Only completed victories can be graded.")
    dev, now = device_id(request), int(time.time())
    conn = db.connect()
    try:
        conn.execute("DELETE FROM submissions WHERE ts<?", (now - int(os.environ.get("RETENTION_DAYS", "90")) * 86400,))
        recent = conn.execute(
            "SELECT COUNT(*) FROM submissions WHERE device=? AND ts>?",
            (dev, now - 3600),
        ).fetchone()[0]
        if recent >= MAX_PER_HOUR:
            raise HTTPException(429, "Too many submissions. Try again later.")
        # exact repeat within 24h -> stored (for the log) but excluded from stats
        dup = conn.execute(
            "SELECT 1 FROM submissions "
            "WHERE device=? AND ts>? AND boss=? AND heals=? AND revives=? "
            "AND charmless=? AND bell=? AND prosthetic=? AND art=? LIMIT 1",
            (
                dev,
                now - 86400,
                run.boss,
                run.heals,
                run.revives,
                int(run.charmless),
                int(run.bell),
                int(run.prosthetic),
                int(run.art),
            ),
        ).fetchone()
        db.insert(
            conn,
            ts=now,
            device=dev,
            boss=run.boss,
            heals=run.heals,
            revives=run.revives,
            charmless=run.charmless,
            bell=run.bell,
            prosthetic=run.prosthetic,
            art=run.art,
            excluded=1 if dup else 0,
            flag_reason="duplicate" if dup else None,
        )
        conn.commit()
        score = db.score_of(run.heals, run.revives)
        # Same response shape whether or not the record was flagged: don't tip off cheaters.
        return {
            "score": score,
            "percentile": cohort_result(conn, run.boss, run.charmless, run.bell, score),
        }
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


# Must be last: catches everything not matched above.
if WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
