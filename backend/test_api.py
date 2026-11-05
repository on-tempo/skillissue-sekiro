"""Smoke test: python test_api.py"""

import os, tempfile, re
from pathlib import Path

# Tests must never touch an environment's production database.
os.environ.pop("DATABASE_URL", None)
os.environ.pop("RAILWAY_ENVIRONMENT", None)
os.environ.pop("RAILWAY_ENVIRONMENT_ID", None)
os.environ.pop("APP_ENV", None)
os.environ["TRUST_PROXY_HEADERS"] = "0"
os.environ["MAX_PER_HOUR"] = "60"
os.environ["WEB_DIR"] = str(Path(__file__).resolve().parent.parent / "web" / "dist")
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["ALLOWED_ORIGINS"] = "http://localhost:4173"
from fastapi.testclient import TestClient
import app as backend, db

c = TestClient(backend.app)
assert c.get("/healthz").json() == {"ok": True, "storage": "sqlite"}
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
# Exact repeat succeeds without another row.
assert c.post("/api/submit", json=ok).json()["submission"] == "duplicate"
conn = db.connect()
assert conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0] == 1
# The cookie survives changing proxy headers and user agent.
identity = c.get("/api/whoami").json()
assert c.get("/api/whoami", headers={"user-agent": "new", "x-real-ip": "1.2.3.4"}).json() == identity
other = TestClient(backend.app)
assert other.get("/api/whoami").json() != identity
other.cookies.set(backend.COOKIE, "tampered")
assert other.get("/api/whoami").status_code == 200
# validation
for bad in [
    dict(ok, heals=-1),
    dict(ok, heals="2"),
    dict(ok, boss="nope"),
    dict(ok, cleared=False),
    dict(ok, revives=100),
]:
    assert c.post("/api/submit", json=bad).status_code == 422, bad
# Rate limit applies to new contributions only.
for i in range(59):
    s = c.post("/api/submit", json=dict(ok, heals=i + 3))
    assert s.status_code == 200, s.text
assert c.post("/api/submit", json=dict(ok, heals=900)).status_code == 429
assert c.post("/api/submit", json=ok).json()["submission"] == "duplicate"
for _ in range(65):
    assert c.get("/api/percentile", params={"boss": "isshin", "score": 90}).status_code == 200
assert conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0] == 60
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
    response = TestClient(backend.app).post('/api/submit', json=dict(ok, boss=boss), headers={'user-agent': 'roster-test-' + boss})
    assert response.status_code == 200, (boss, response.text)
for alias, canonical in db.BOSS_ALIASES.items():
    response = TestClient(backend.app).post('/api/submit', json=dict(ok, boss=alias), headers={'user-agent': 'alias-' + alias})
    assert response.status_code == 200, (alias, response.text)
assert c.get('/privacy.html').status_code == 200
for patch in [dict(ok, heals=True), dict(ok, charmless='false'), dict(ok, heals=0.5)]:
    assert c.post('/api/submit', json=patch).status_code == 422
# Untrusted forwarded IP headers must not bypass device rate limits.
assert c.get('/api/whoami', headers={'x-real-ip':'1.2.3.4'}).json() == c.get('/api/whoami', headers={'x-real-ip':'5.6.7.8'}).json()
conn.close()
print('14 bosses, legacy aliases, strict types, privacy page, and proxy defaults passed.')
# Concurrent identical submissions with the same established cookie count once.
from concurrent.futures import ThreadPoolExecutor
visitor = TestClient(backend.app)
visitor.get('/api/whoami')
cookie = visitor.cookies.get(backend.COOKIE)
def concurrent_submit(_):
    with TestClient(backend.app) as client:
        client.cookies.set(backend.COOKIE, cookie)
        return client.post('/api/submit', json=dict(ok, heals=777))
with ThreadPoolExecutor(max_workers=8) as pool:
    responses = list(pool.map(concurrent_submit, range(8)))
assert all(r.status_code == 200 for r in responses)
assert sum(r.json()['submission'] == 'saved' for r in responses) == 1

# One aggregate statement, ties, low sample count, and rank bounds.
class Snapshot:
    def __init__(self, n, better): self.values, self.calls = (n, better), 0
    def execute(self, sql, params):
        self.calls += 1
        assert 'SUM(CASE WHEN' in sql
        return self
    def fetchone(self): return self.values
for n, better, expected in [(20, 0, 5), (20, 19, 100), (20, 20, 100), (60, 6, 12)]:
    snapshot = Snapshot(n, better)
    assert backend.cohort_result(snapshot, 'ape', False, False, 90)['top_percent'] == expected
    assert snapshot.calls == 1
assert backend.cohort_result(Snapshot(19, 0), 'ape', False, False, 90)['status'] == 'collecting'

# Production must not silently fall back to SQLite.
import subprocess, sys
prod = dict(os.environ, APP_ENV='production', DEVICE_SECRET='a' * 64)
check = subprocess.run([sys.executable, '-c', 'import app'], env=prod, capture_output=True, text=True)
assert check.returncode != 0 and 'DATABASE_URL is required' in check.stderr
print('Stable cookies, free lookups, 60/hour contributions, concurrency, rank bounds and production guard passed.')

# Old records do not unlock a cohort; conditions remain separate.
conn = db.connect()
for i in range(20):
    db.insert(conn, ts=int(time.time()) - 91 * 86400, device=f'old-{i}', boss='emma',
              heals=0, revives=0, charmless=True, bell=True, prosthetic=False, art=False)
conn.commit()
assert backend.cohort_result(conn, 'emma', True, True, 100)['n'] == 0
conn.close()

# Detection is read-only even for a legacy caller passing dry=False.
from unittest.mock import patch
import pandas as pd
import numpy as np
import detect
features = pd.DataFrame([
    dict(device=f'd{i}', n=5, log_n=1.0, max_per_hour=5, frac_perfect=1.0,
         dup_share=0.2, n_bosses=5, log_median_gap=1.0, mean_score=100, std_score=0.0)
    for i in range(30)
]).set_index('device')
class ReadOnly:
    def execute(self, *args): raise AssertionError('Detector attempted a database write')
    def executemany(self, *args): raise AssertionError('Detector attempted a database write')
    def commit(self): raise AssertionError('Detector attempted a database commit')
with patch.object(detect, 'build_features', return_value=features), patch.object(detect, 'IsolationForest') as factory:
    factory.return_value.predict.return_value = -np.ones(30)
    factory.return_value.score_samples.return_value = -np.ones(30)
    assert len(detect.run(ReadOnly(), dry=False)) == 30
print('Retention/cohort separation and report-only anomaly detection passed.')
