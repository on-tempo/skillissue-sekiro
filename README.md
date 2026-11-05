# skillissue.gg — Sekiro

A full-stack web app for recording, assessing, and sharing Sekiro boss victories. Enter your clear conditions, see how the grade was calculated, and compare your record with submissions for the same boss and challenge settings.

**[Open the app](https://skillissue-sekiro-production.up.railway.app/)**

## Features

- **14 bosses:** searchable selection, including separate entries for both Isshin encounters and both Monk encounters.
- **Clear conditions:** healing uses, resurrections, Charmless, Demon Bell, Prosthetic tools, and Combat Arts.
- **Transparent grading:** a provisional resource-use score with an explanation of every deduction.
- **Condition-specific rankings:** separate cohorts for each boss × Charmless × Demon Bell combination; percentiles appear after 20 eligible submissions.
- **Shareable records:** URL-based input sharing and downloadable PNG cards.
- **Responsive UI:** moonlit teal and silver styling, katana/full-moon artwork, and mobile-friendly count controls.
- **Submission safeguards:** server-side validation and scoring, hourly submission limits, duplicate exclusion, and an offline anomaly-detection pipeline.
- **Backup tooling:** a separate PostgreSQL-to-S3 job, checksum manifests, and a restore-verification tool for an empty test database.

Records are self-reported. The application does not collect game telemetry or verify that a boss was defeated.

## Tech stack

| Layer | Technologies |
| --- | --- |
| Frontend | React 19, TypeScript, Vite, CSS, Canvas API |
| API | Python, FastAPI, Pydantic |
| Storage | PostgreSQL; SQLite for local development |
| Data processing | Pandas, NumPy, scikit-learn Isolation Forest |
| Packaging and hosting | Multi-stage Docker build, Railway |
| CI | GitHub Actions: frontend, API, container, and backup checks |
| Backup tooling | PostgreSQL client tools, Boto3, AWS S3 |

## Architecture

```mermaid
flowchart TD
    Browser[Browser: React and TypeScript] -->|HTTP| Web[FastAPI: API and built web assets]
    Web --> DB[(PostgreSQL)]
    Maintenance[Separate maintenance job] -->|Cleanup and anomaly flags| DB
    DB -->|pg_dump snapshot| Backup[Separate backup job]
    Backup -->|Archive and checksum manifest| S3[Private AWS S3 bucket]
```

The production image serves the compiled frontend and API from one origin. During development, Vite runs on port 5173 and proxies API requests to FastAPI on port 8000. Local storage defaults to SQLite when `DATABASE_URL` is absent.

Maintenance and backup jobs require separately configured services. Deploying the web service does not activate either job. The presence of backup code is not proof that uploads or restores have succeeded; verify a completed run and a real test restore before relying on the backup.

## Run locally

Use Node.js 22.12+ within the 22 release line, or Node.js 24, and Python 3.12 or 3.13. Run commands from the repository root unless a step changes directories.

### Install dependencies

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

cd web
npm ci
cd ..
```

On Windows, activate the environment with `.venv\Scripts\activate` instead.

### Development: two terminals

Terminal 1 — API:

```sh
source .venv/bin/activate
cd backend
uvicorn app:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Terminal 2 — frontend:

```sh
cd web
npm run dev
```

Open **http://localhost:5173**. Keep both terminals running to submit records and retrieve community rankings. Stop each server with `Ctrl+C`.

### Serve the production build locally

```sh
cd web
npm run build
cd ../backend
uvicorn app:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

With the Python environment active, open **http://localhost:8000**. Stop any existing server using port 8000 first. This mode does not need Vite; rebuild after frontend changes. FastAPI serves `web/dist/`, not the TypeScript source files.

## Scoring and rankings

```text
score = max(0, 100 - healing_uses × 5 - resurrections × 15)
```

| Grade | Score |
| --- | --- |
| S | 95–100 |
| A | 80–94 |
| B | 60–79 |
| C | 0–59 |

Charmless and Demon Bell do not add points. They define separate ranking cohorts. Prosthetic tools and Combat Arts are displayed on the card without a score penalty.

Scores describe resource use under the site's provisional rules, not overall player skill. They do not normalize boss difficulty, other character stats, or item effects. Zero healing does not imply a no-hit run.

Only an explicit **Reveal** action submits a record. Initial examples and opening shared links do not create submissions. Successful responses for identical inputs are cached for the current page load. Exact repeats from the same device key within 24 hours are stored but excluded from the percentile cohort.

The API computes scores independently of the frontend. Percentiles compare eligible site submissions for the same boss and challenge conditions; they are not global Sekiro player rankings.

## Submission filtering

The API rejects invalid values, unsupported bosses, and records not marked as cleared. By default, a device key can submit at most 10 records per hour.

`backend/detect.py` is a batch process that:

1. Groups eligible submissions by a pseudonymous device key.
2. Computes eight behavior features: submission count, peak hourly volume, perfect-record share, repeated-record share, boss variety, median time gap, mean score, and score variation.
3. Fits a 300-tree Isolation Forest with a default contamination setting of 0.10.
4. Excludes records only when the model flags the device key **and** an explainable rule matches.

The additional rules look for hourly bursts, repeated identical records, or a high share of zero-healing/zero-resurrection records. The model requires at least 30 device keys with three eligible submissions each. Exclusion reasons are saved as `ml:<reason>`; records are not deleted or accounts banned.

Device keys are derived from IP and user-agent data using HMAC. Shared networks and VPNs can affect their reliability. Forwarded client-IP headers are ignored by default; only enable trust after verifying the reverse proxy configuration.

One-shot fabricated records may go undetected, and legitimate submissions can be flagged. Synthetic evaluation measures behavior on the included generator, not production fraud-detection accuracy.

## Tests and CI

Build the frontend before running the API tests:

```sh
# Repository root; Python virtual environment active
npm --prefix web run build

cd backend
python test_api.py
python simulate.py
python detect.py --dry-run
cd ..

python -m unittest discover -s backup -p 'test_*.py' -v
```

- `test_api.py` uses a temporary SQLite database and checks built assets, source-file exclusion, validation, scoring, duplicate handling, rate limits, and percentile responses.
- `simulate.py` evaluates anomaly detection using an isolated synthetic dataset; it does not populate the application database.
- `detect.py --dry-run` reads the configured database and reports candidates without applying flags. Small datasets are skipped.
- Backup tests mock database tools and uploads. They do not establish that real PostgreSQL or S3 access works.

The GitHub Actions workflow checks frontend types/builds, API behavior, both Docker images, and backup/restore safeguards. Check the workflow run for its actual status. Live PostgreSQL connectivity, cloud credentials, and a real restore require separate verification.

## Deployment

The root `Dockerfile` builds React in a Node stage and copies only `web/dist/` into the Python runtime image. FastAPI listens on Railway's `PORT` and exposes `/healthz` for readiness checks.

| Service | Build | Start command | Intended schedule |
| --- | --- | --- | --- |
| Web | `Dockerfile` | Dockerfile CMD | Long-running |
| Maintenance | `Dockerfile` | `sh -c "python cleanup.py && python detect.py"` | Hourly, if configured |
| Backup | `Dockerfile.backup` | `python backup.py` | Daily at 07:00 UTC, if configured |

Each service uses the repository root as its build context. For the backup service, set `RAILWAY_DOCKERFILE_PATH=Dockerfile.backup`. It needs no public domain or HTTP healthcheck. Configure its start command, cron schedule, and restart policy (`Never`) in the service settings.

The `railway*.json` files record intended deployment settings. For new services, use Railway's currently supported configuration mechanism rather than assuming legacy JSON files will be applied. See the [Railway configuration documentation](https://docs.railway.com/config-as-code).

### Web environment

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection string; absent means SQLite |
| `DEVICE_SECRET` | HMAC secret; required when `DATABASE_URL` or `RAILWAY_ENVIRONMENT` is set |
| `WEB_DIR` | Built asset directory; Docker sets `/app/web/dist` |
| `MAX_PER_HOUR` | Submission limit; default `10` |
| `RETENTION_DAYS` | Submission retention; default `90` |
| `TRUST_PROXY_HEADERS` | Defaults to `0`; enable only for a verified trusted proxy |

Environment examples document variable names; `.env` files are not automatically loaded. Keep actual connection strings and credentials out of Git. SQLite records are not automatically migrated when switching to PostgreSQL.

Use one web replica for the current implementation. The rate-limit check and insert are not an atomic distributed limiter, and schema initialization is not a migration framework.

### S3 backup environment

The backup service needs its own `DATABASE_URL`, `BACKUP_S3_BUCKET`, `BACKUP_S3_PREFIX`, `AWS_DEFAULT_REGION`, and AWS credentials. Prefix-scoped IAM upload policy and S3 lifecycle templates are included under `backup/`.

The job creates a custom-format PostgreSQL archive, checks its table-of-contents listing, uploads it using SSE-S3 encryption, and then writes a JSON manifest with its size and SHA-256 checksum. A matching archive and manifest mark a completed upload. `--dry-run` validates configuration only, without contacting PostgreSQL or AWS.

`restore_verify.py` checks archive size/checksum and restores only into an explicitly selected empty test database. It never runs `DROP` or `--clean`. Do not use the production database as a restore-test target. See [BACKUP_SETUP.md](BACKUP_SETUP.md) for scripts and templates; use current Railway service settings for scheduling.

Daily snapshots are not continuous replication or automatic failover. Backup retention, failed-run monitoring, and restore drills must be configured separately. Restoring an old snapshot can reintroduce expired records; reapply cleanup before returning a restored database to service.

## Project structure

```text
.github/workflows/ci.yml   Build, API, container, and backup checks
backend/
  app.py                  FastAPI routes and built frontend hosting
  db.py                   SQLite/PostgreSQL storage and server scoring
  detect.py               Batch anomaly detection
  cleanup.py              Retention cleanup
  simulate.py             Synthetic evaluation
  test_api.py             API and built-asset integration tests
web/
  src/
    PageChrome.tsx        Header, hero, footer
    ScoreApp.tsx          Draft/record state and submission lifecycle
    BossSelector.tsx      Searchable boss selection
    CountInput.tsx        Bounded count controls
    ResultCard.tsx        Result presentation
    downloadCard.ts       PNG export
    run.ts                Shared-link parsing and record helpers
  scoring.mjs             Boss registry and frontend scoring
  scoring.d.mts           Type declarations for the scoring module
  vite.config.ts          Build configuration and development API proxy
backup/
  backup.py               PostgreSQL snapshot and S3 upload
  restore_verify.py       Empty-target restore verification
  test_*.py               Offline safeguard tests
  requirements.txt        Backup-specific Python dependency
  iam-upload-policy.json  Prefix-scoped upload policy template
  s3-lifecycle.json       Backup expiry template
Dockerfile                Web production image
Dockerfile.backup         Standalone backup job image
```

## Current scope

- Boss-rematch records only; no story-mode normalization or game-account integration.
- Shared links encode editable input values, not verified or immutable database records.
- Social previews use a shared static image; per-record Open Graph images are not implemented.
- No live advertising or analytics trackers are included.
- Privacy notice and retention settings must match the actual hosting and backup setup.

Unofficial fan project. Not affiliated with FromSoftware or Activision.
