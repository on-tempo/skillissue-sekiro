# Backend

FastAPI serves the built frontend and API. Production uses PostgreSQL; local development defaults to SQLite. See the root README for dependency installation and the React build.

## API flow

- `GET /api/percentile`: read-only comparison for the same boss × Charmless × Demon Bell settings. Reveal uses this endpoint without saving a record.
- `POST /api/submit`: used by Contribute this clear. Validates the input and recalculates the score before saving. The default limit is 60 new contributions per anonymous visitor per hour.
- Exact repeats within 24 hours return `submission: duplicate` without adding a row or consuming another quota slot.
- `GET /api/whoami`: short diagnostic identifier derived from the visitor cookie.
- `GET /healthz`: database connectivity and storage type (`postgresql` or `sqlite`).

A signed HttpOnly cookie provides an anonymous visitor identifier for up to 30 days. It is independent of proxy IP and user agent. Clearing cookies creates a new identity, so this is a soft contribution limit, not a way to identify unique players.

PostgreSQL advisory transaction locks serialize each visitor's duplicate check, quota check and insert. SQLite uses `BEGIN IMMEDIATE`. Production refuses to start without `DATABASE_URL` and a random `DEVICE_SECRET` of at least 32 characters. Replicas must share the same database and secret.

## Rankings

At least 20 eligible records are needed in a cohort. Below that, the response reports `collecting`, the current count and the minimum count. Expired and excluded records do not count.

Top percentage is `ceil(100 * (strictly better records + 1) / total records)`, bounded to 1–100. Ties share a rank. It compares submitted records, not verified player skill. Charmless and Demon Bell define separate cohorts rather than adding points.

## Maintenance

Run these commands from `backend/` with the Python environment active:

```sh
python cleanup.py
python detect.py
```

Cleanup deletes records older than `RETENTION_DAYS` (default 90). Schedule it separately; rankings filter out expired rows even before cleanup runs.

The detector computes behavior features and runs Isolation Forest when at least 30 visitor keys have three submissions each. A model outlier with an explainable signal becomes a review candidate. Both normal execution and `--dry-run` leave database flags unchanged. Historical ML exclusions remain until separately reviewed.

Candidates do not prove cheating. Self-reported inputs, cookie resets and isolated fabricated runs limit detection. Simulation results describe the synthetic generator, not production accuracy.

## Tests

From the repository root:

```sh
npm --prefix web run build
(cd backend && python test_api.py)
(cd backend && python simulate.py)
```

`test_api.py` uses temporary SQLite storage. `simulate.py` uses its own synthetic dataset.

`test_postgres.py` requires an explicit `TEST_DATABASE_URL`. It accepts only loopback hosts and database names beginning with `skillissue_test_`; never supply a production URL. It creates a random schema and removes only that schema when finished.

```sh
# After setting TEST_DATABASE_URL to a disposable local PostgreSQL database:
(cd backend && python test_postgres.py)
```

GitHub Actions provides a disposable PostgreSQL 18 service. Tests cover persistence through a separate connection, simultaneous duplicate submissions, concurrent submissions at the hourly limit, read-only ranking lookup and separate challenge cohorts. No Railway or AWS credentials are needed in CI.
