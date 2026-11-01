# skillissue.gg backend (percentile + anomaly detection)

```sh
pip install -r requirements.txt
python test_api.py                       # API smoke test
python simulate.py                       # detector evaluation on synthetic data
DEVICE_SECRET=$(openssl rand -hex 32) uvicorn app:app --port 8000
python detect.py --dry-run               # review flags first
python detect.py                         # apply (run via cron, e.g. hourly)
```

## Flow
- `POST /api/submit` validates (same rules as `scoring.mjs`), computes the score **server-side**, applies
  realtime rules (10/hour rate limit, 24h exact-duplicate exclusion), stores the raw log.
- `GET /api/percentile` returns "top N%" within `boss x charmless x bell`, excluding flagged rows,
  and `collecting` until the cohort has 20+ records.
- `detect.py` (offline): per-device features -> Isolation Forest -> flag only if outlier AND an explainable rule fires.
  Flagged records are excluded from stats, not deleted. Every flag has a human-readable reason.

## Known limits (read before trusting it)
- **One-shot perfect submissions are invisible** (stealth = 0% in simulation). Behaviour-based detection needs
  several submissions per device. Self-reported data cannot be fully protected; keep the "self-reported" wording.
- Slow farmers are mostly missed at contamination 0.10 (raising it trades recall for false positives).
- Devices are `HMAC(ip|user-agent)`: shared IPs (dorms, cafes) with identical browsers can look like one heavy user,
  and VPN users can look like many. Never auto-ban; review flags.
- Simulation numbers depend on the generator in `simulate.py`. Re-tune `contamination` and the rule thresholds on real data.
- Hashed IPs are still personal data in some jurisdictions (GDPR). Add a privacy notice and a retention limit.
- Percentile responses look identical for flagged/unflagged records on purpose.

## Frontend integration
The web app submits once per explicit Reveal action and caches identical runs in the browser session. New records do not get submitted when opening a shared link or the initial example. See the root README for running the combined service.
