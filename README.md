# skillissue.gg — integrated Sekiro project

English UI, moonlit teal/silver palette, katana/full-moon artwork, 14 bosses, PNG cards and shareable record links. Includes FastAPI, local SQLite / optional PostgreSQL, server-side scoring, community percentiles, submission limits, duplicate exclusion, and an offline Isolation Forest job.

## Start locally (macOS / Linux)

From this project root:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
uvicorn app:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Open http://localhost:8000. The same service serves both web pages and `/api/*`; a separate static server is not needed. Local data goes in `backend/skillissue.db`. `.env.example` documents variables; environment files are not automatically loaded.

Windows activation: `.venv\Scripts\activate`, then use the same remaining commands.

## Project map

- `web/`: HTML, CSS, JS, 14-boss registry, SVG artwork, social image, favicon, privacy page.
- `backend/app.py`: validation, submit/percentile APIs, rate limit, same-origin static hosting.
- `backend/db.py`: SQLite/PostgreSQL storage, server scoring, legacy ID aliases.
- `backend/detect.py`: offline anomaly review; excludes records without deleting them.
- `backend/cleanup.py`: retention cleanup, defaults to 90 days.
- `backend/simulate.py`: isolated synthetic detector evaluation; never seeds production.
- `backend/test_api.py`: integration checks using a temporary SQLite database.
- `Dockerfile`, `railway.json`, `railway.cron.json`: web + hourly maintenance deployment.

## Verify

```sh
# With the virtual environment active, from backend/:
python test_api.py
python simulate.py
python detect.py --dry-run
```

## Community ranking

Only an explicit Reveal submits a record. Initial examples and opening shared links do not submit. Repeated identical input is cached in the browser session. Backend duplicates within 24 hours are excluded from the statistical cohort. The server computes scores; it ignores any client-supplied score.

Cohorts use boss × Charmless × Demon Bell. Rankings appear only at 20 eligible records. Scores use max(0, 100 − healing×5 − resurrections×15), with S≥95, A≥80, B≥60, C otherwise. These provisional rules and site-submitted records do not establish a global player ranking. All records are self-reported.

The alias IDs `headless`, `monk`, `truemonk`, `dragon`, `hatred` from the supplied ZIP map to the previous project's canonical IDs. All original 14 IDs remain valid, including Emma and Isshin Ashina.

## Railway configuration

Use the project root as the repository root. Deploy the Dockerfile for the web service, add PostgreSQL, then set `DATABASE_URL` and a strong `DEVICE_SECRET` in the service variables. Generate a secret locally with `openssl rand -hex 32`; never commit it. Production refuses the development default secret. Configure your generated domain and replace `https://skillissue.gg/` in `web/index.html` metadata with that actual domain.

For the scheduled service, use the same repository and database, select `/railway.cron.json` as its config file. Its command runs cleanup followed by detection. Use one web replica for this first release. No Railway account changes or live backend deployment have been performed as part of packaging this project.

Forwarded client-IP headers are ignored by default. Only set `TRUST_PROXY_HEADERS=1` after checking that your deployed reverse proxy overwrites these headers and prevents direct access. Also configure Uvicorn proxy handling deliberately; the local example disables it. Device keys use HMAC(IP + user-agent), which can group shared networks or split VPN users. `/api/whoami` offers a short diagnostic key, not authentication.

## Detection and privacy limits

Isolation Forest needs at least 30 devices with 3 submissions each. An ML outlier is excluded only when an explainable rule also fires. Stored ML reasons use `ml:<reason>`; manual and duplicate flags are preserved. It cannot verify actual gameplay or reliably catch a single invented perfect score. Review results before relying on them.

Submission logs are pruned during submissions and by scheduled cleanup. Set `RETENTION_DAYS` consistently on web and cron services. Update `web/privacy.html` if changing retention, and supply operator contact information before a public launch. No live ads or analytics are integrated. Hosting access logs and backups have their own policies.

## Validation for this integrated delivery

See `VALIDATION.md` for checks run on this version. Claims of prior PostgreSQL or Railway tests in supplied documents are not evidence of tests performed for this delivery.
