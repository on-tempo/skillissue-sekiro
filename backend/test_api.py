"""Smoke test: python test_api.py"""

import os, tempfile, re
from pathlib import Path

# Tests must never touch an environment's production database.
os.environ.pop("DATABASE_URL", None)
os.environ.pop("RAILWAY_ENVIRONMENT", None)
os.environ["TRUST_PROXY_HEADERS"] = "0"
os.environ["MAX_PER_HOUR"] = "10"
os.environ["WEB_DIR"] = str(Path(__file__).resolve().parent.parent / "web" / "dist")
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["ALLOWED_ORIGINS"] = "http://localhost:4173"
from fastapi.testclient import TestClient
import app as backend, db

c = TestClient(backend.app)
assert c.get("/healthz").json() == {"ok": True}
assert c.get("/").status_code == 200 and "skillissue" in c.get("/").text
html = c.get("/").text
scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)
styles = re.findall(r'<link[^>]+href="([^"]+\.css)"', html)
assert scripts and styles, "Build the React frontend before running API tests."
for url in scripts + styles:
    asset = c.get(url)
    assert asset.status_code == 200, url
    assert ("javascript" if url.endswith(".js") else "text/css") in asset.headers["content-type"]
assert '/src/main.tsx' not in html
for private_path in ['/src/ScoreApp.tsx', '/package.json', '/app.js', '/scoring.mjs', '/backend/app.py']:
    assert c.get(private_path).status_code == 404, private_path
for asset_path in ['/privacy.html', '/og-image.png', '/apple-touch-icon.png', '/moon-katana-mark.svg']:
    assert c.get(asset_path).status_code == 200, asset_path
assert len(c.get("/api/whoami").json()["device"]) == 6
ok = dict(
    boss="isshin",
    heals=2,
    revives=0,
    charmless=False,
    bell=False,
    prosthetic=True,
    art=False,
    cleared=True,
)

r = c.post("/api/submit", json=ok)
assert r.status_code == 200, r.text
assert r.json()["score"] == 90 and r.json()["percentile"]["status"] == "collecting"
# exact repeat is stored but excluded from stats; response looks identical
assert c.post("/api/submit", json=ok).status_code == 200
conn = db.connect()
assert (
    conn.execute(
        "SELECT COUNT(*) FROM submissions WHERE excluded=1 AND flag_reason='duplicate'"
    ).fetchone()[0]
    == 1
)
# validation
for bad in [
    dict(ok, heals=-1),
    dict(ok, heals="2"),
    dict(ok, boss="nope"),
    dict(ok, cleared=False),
    dict(ok, revives=100),
]:
    assert c.post("/api/submit", json=bad).status_code == 422, bad
# rate limit: 10/hour per device
for i in range(20):
    s = c.post("/api/submit", json=dict(ok, heals=i + 3))
assert s.status_code == 429
# percentile once cohort is big enough (seed other devices directly)
import time

for i in range(60):
    db.insert(
        conn,
        ts=int(time.time()),
        device=f"x{i}",
        boss="ape",
        heals=i % 10,
        revives=0,
        charmless=False,
        bell=False,
        prosthetic=True,
        art=False,
    )
conn.commit()
p = c.get("/api/percentile", params=dict(boss="ape", score=95)).json()
assert p["status"] == "ok" and 1 <= p["top_percent"] <= 100, p
print("all API checks passed;", p)

# Each supported boss must survive server validation and keep its own cohort.
for boss in db.BOSSES:
    response = c.post('/api/submit', json=dict(ok, boss=boss), headers={'user-agent': 'roster-test-' + boss})
    assert response.status_code == 200, (boss, response.text)
for alias, canonical in db.BOSS_ALIASES.items():
    response = c.post('/api/submit', json=dict(ok, boss=alias), headers={'user-agent': 'alias-' + alias})
    assert response.status_code == 200, (alias, response.text)
assert c.get('/privacy.html').status_code == 200
for patch in [dict(ok, heals=True), dict(ok, charmless='false'), dict(ok, heals=0.5)]:
    assert c.post('/api/submit', json=patch).status_code == 422
# Untrusted forwarded IP headers must not bypass device rate limits.
assert c.get('/api/whoami', headers={'x-real-ip':'1.2.3.4'}).json() == c.get('/api/whoami', headers={'x-real-ip':'5.6.7.8'}).json()
conn.close()
print('14 bosses, legacy aliases, strict types, privacy page, and proxy defaults passed.')