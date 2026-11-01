# Checks for this integrated delivery

Passed locally with Python 3.12 and SQLite:

- API smoke/integration test: static HTML, JavaScript module MIME, health check, server score, strict validation, duplicate exclusion, hourly limit, percentile query.
- Additional checks: 14 bosses, legacy aliases, privacy page, forwarded-header default.
- Frontend JavaScript syntax checks.
- Browser: page loaded with 14 bosses; explicit Reveal called the real API and displayed the 20-record threshold with 1 submitted record.
- Synthetic anomaly simulation: 20/20 spammer devices, 14/15 repeaters, 1/15 slow farmers flagged; 1/1570 normal devices flagged; 0/100 one-shot fabricated perfect devices flagged. These figures are properties of this synthetic generator, not production accuracy.
- Source ZIP checked for corrupt members and excluded virtualenvs, database files, bytecode, credentials, and nested duplicate ZIPs.

Not tested: a live PostgreSQL server, Railway deployment, or Docker image build. Docker CLI was available but its daemon was not running. This delivery does not inherit the supplied README's historical claims about PostgreSQL tests. The existing Sites publication has not been replaced with this Python backend.

The test environment's resolved dependency versions are recorded in requirements-lock.txt; backend/requirements.txt lists direct dependencies. Platform-specific wheels may differ on Linux.
