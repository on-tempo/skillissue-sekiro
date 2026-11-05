# Railway PostgreSQL → S3 backup

The web service writes to PostgreSQL. A separate Railway job runs `pg_dump` and uploads an archive plus a checksum manifest to a private S3 bucket. Deploying the web service does not enable this job.

## 1. Check the database

Open the web service's `/healthz`. The expected response is:

```json
{"ok": true, "storage": "postgresql"}
```

The web and backup services must reference the same PostgreSQL service and environment through their own `DATABASE_URL` variables. Existing SQLite records are not automatically migrated.

## 2. Configure S3 and IAM

For this project, the intended bucket is `skillissue-backups-sekiro` in `us-east-1`. Confirm it in your AWS console.

Keep Block Public Access enabled, ACLs disabled and default SSE-S3 encryption enabled. If versioning is enabled, configure expiry of both current and noncurrent versions. The template in `backup/s3-lifecycle.json` targets `postgres/`: current versions expire after 30 days, noncurrent versions after one day, and abandoned multipart uploads after one day. Lifecycle deletion is asynchronous. Do not overwrite rules for unrelated data.

`backup/iam-upload-policy.json` is a template for the backup identity. Replace the bucket placeholder when creating the IAM policy. It allows uploads and aborting multipart uploads under the backup prefix, not listing, reading or deleting backups. Use separate operator access to inspect or download backups. Keep AWS credentials in Railway variables, outside Git and screenshots.

## 3. Configure the separate Railway backup service

Connect the same repository and environment, with the repository root as the build context. Configure the service settings directly and verify their effective values; do not assume a legacy JSON configuration was applied.

| Setting | Value |
| --- | --- |
| Variable `RAILWAY_DOCKERFILE_PATH` | `Dockerfile.backup` |
| Start command | `python backup.py` |
| Cron schedule | `0 7 * * *` (daily, 07:00 UTC) |
| Restart policy | Never |
| Public domain / HTTP healthcheck | None |

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | Reference to the production PostgreSQL service, e.g. `${{Postgres.DATABASE_URL}}` |
| `BACKUP_S3_BUCKET` | `skillissue-backups-sekiro` |
| `BACKUP_S3_PREFIX` | `postgres/` |
| `AWS_DEFAULT_REGION` | `us-east-1` |
| `AWS_ACCESS_KEY_ID` | Backup-only IAM access key |
| `AWS_SECRET_ACCESS_KEY` | Its secret key |
| `BACKUP_SSLMODE` | `require` by default |

The service name in a reference variable must match your project. `DEVICE_SECRET` is not needed by the backup job. The backup image includes PostgreSQL client 18; it cannot dump a newer major server. The script requires TLS; `require` encrypts traffic, while certificate identity verification needs an appropriately configured `verify-full` connection.

## 4. Confirm an actual upload

Run the backup service once using Railway's manual cron execution. A successful run exits with code 0 and prints:

```json
{"status":"backup_uploaded","archive_key":"postgres/...dump","size_bytes":12345,"sha256":"..."}
```

The size and hash above are placeholders, not evidence of an actual backup.

In the S3 console, open the matching `postgres/YYYY/MM/DD/` prefix. Confirm:

1. The `.dump` archive and same-basename `.json` manifest both exist.
2. The manifest's `archive_key` matches the archive.
3. `size_bytes` matches the archive size and `uploaded_at` is recent.

The manifest is written only after the archive upload completes. An archive without its manifest is not a confirmed completed run. `--dry-run` checks configuration strings only; it does not contact the database or AWS.

Upload-only IAM credentials cannot list the bucket. Inspect it using operator access instead of expanding the backup identity's permissions.

## 5. Verify restoration separately

Download a matching archive and manifest to the Git-ignored `backup-downloads/` directory. Prepare an empty PostgreSQL test database separate from production, preferably using the same major version as production.

Set `RESTORE_DATABASE_URL` to that test database privately. With Python 3.11+, `pg_restore` and `psql` installed, run from the repository root:

```sh
python backup/restore_verify.py backup-downloads/example.dump backup-downloads/example.json --confirm-empty-target
```

Replace the two filenames with your downloaded files. The tool checks size, SHA-256 and archive readability, rejects a nonempty target, restores in a single transaction and checks that `public.submissions` is queryable. It does not use `--clean` or `DROP`.

When `DATABASE_URL` is also set, a matching source host/port/database is rejected. Aliases can defeat this comparison, so verify the restore target yourself. Never point `RESTORE_DATABASE_URL` at production. Check restored record counts and representative records before treating recovery as verified. Old snapshots can reintroduce expired records; apply retention cleanup before exposing a restored database.

## 6. Track evidence and failures

Record the last successful upload time and archive key, and separately the last successful test restore. A green web deployment, passing CI or an existing S3 bucket proves neither.

The job returns exit code 1 on failure. Check Railway job logs and the age of the latest completed manifest. Automatic failure notifications are not implemented. A daily backup is a snapshot, not continuous replication or automatic failover; failed or delayed runs increase the potential data-loss window.

Offline safeguards can be checked with:

```sh
python -m unittest discover -s backup -p 'test_*.py' -v
```

These mocked tests do not establish that cloud credentials, real uploads or restores work. This document does not claim those operations have succeeded. Align the site's privacy notice with the retention and backup configuration actually in use.

## References

- [Railway cron jobs](https://docs.railway.com/cron-jobs)
- [Railway restart policy](https://docs.railway.com/deployments/restart-policy)
- [PostgreSQL pg_dump](https://www.postgresql.org/docs/current/app-pgdump.html)
- [S3 Lifecycle](https://docs.aws.amazon.com/AmazonS3/latest/userguide/intro-lifecycle-rules.html)
