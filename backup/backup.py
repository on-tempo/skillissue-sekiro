"""Daily PostgreSQL -> private S3 backup. Never prints connection strings."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from urllib.parse import parse_qs, unquote, urlsplit
from uuid import uuid4


class BackupError(Exception):
    pass


def postgres_env(url: str) -> dict[str, str]:
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in ('postgres', 'postgresql'):
            raise ValueError()
        if not parsed.hostname or not parsed.username or not parsed.path.strip('/'):
            raise ValueError()
        if not parsed.password:
            raise ValueError()
        query = parse_qs(parsed.query, keep_blank_values=True)
        allowed = {'sslmode', 'sslrootcert', 'connect_timeout'}
        if set(query) - allowed or any(len(values) != 1 for values in query.values()):
            raise ValueError()
        sslmode = query.get('sslmode', [os.environ.get('BACKUP_SSLMODE', 'require')])[0]
        if sslmode not in ('require', 'verify-ca', 'verify-full'):
            raise ValueError()
        env = os.environ.copy()
        # An inherited libpq option must not redirect a job to a different database.
        for key in list(env):
            if key.startswith('PG'):
                del env[key]
        env.update(
            PGHOST=parsed.hostname, PGPORT=str(parsed.port or 5432),
            PGUSER=unquote(parsed.username), PGPASSWORD=unquote(parsed.password),
            PGDATABASE=unquote(parsed.path[1:]), PGSSLMODE=sslmode,
            PGCONNECT_TIMEOUT=query.get('connect_timeout', ['15'])[0], PGAPPNAME='skillissue-backup',
        )
        if 'sslrootcert' in query:
            env['PGSSLROOTCERT'] = query['sslrootcert'][0]
        return env
    except (ValueError, TypeError):
        raise BackupError('Invalid DATABASE_URL or unsupported connection options.') from None


def settings() -> tuple[dict[str, str], str, str, str]:
    env = postgres_env(os.environ.get('DATABASE_URL', ''))
    bucket = os.environ.get('BACKUP_S3_BUCKET', '')
    region = os.environ.get('AWS_DEFAULT_REGION', '')
    prefix = os.environ.get('BACKUP_S3_PREFIX', 'postgres/').strip('/')
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]', bucket):
        raise BackupError('Set BACKUP_S3_BUCKET to a valid bucket name.')
    if not region or not re.fullmatch(r'[a-z0-9-]+', region):
        raise BackupError('Set AWS_DEFAULT_REGION to the bucket region.')
    if not prefix or not re.fullmatch(r'[a-zA-Z0-9/_-]+', prefix) or '..' in prefix:
        raise BackupError('Set a non-empty BACKUP_S3_PREFIX, for example postgres/.')
    return env, bucket, region, prefix + '/'


def command(args: list[str], env: dict[str, str], timeout: int = 900) -> None:
    try:
        subprocess.run(args, env=env, capture_output=True, check=True, timeout=timeout)
    except FileNotFoundError:
        raise BackupError('PostgreSQL client tools are missing. Use Dockerfile.backup.') from None
    except subprocess.TimeoutExpired:
        raise BackupError('PostgreSQL backup operation timed out; no completed backup uploaded.') from None
    except subprocess.CalledProcessError:
        # Tool stderr can contain hostnames or connection details. Keep it out of cron logs.
        raise BackupError('PostgreSQL tool failed. Check connectivity, TLS, credentials and client/server versions.') from None


def create_archive(path: Path, env: dict[str, str]) -> None:
    command(['pg_dump', '--no-password', '--format=custom', '--compress=6',
             '--no-owner', '--no-acl', '--file', str(path)], env)
    if not path.is_file() or path.stat().st_size == 0:
        raise BackupError('pg_dump produced no archive.')
    command(['pg_restore', '--list', str(path)], env)


def upload_archive(client, path: Path, bucket: str, prefix: str, started: str) -> dict:
    with path.open('rb') as source:
        checksum = hashlib.file_digest(source, 'sha256').hexdigest()
    now = datetime.now(timezone.utc)
    run_id = now.strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex
    base = f'{prefix}{now:%Y/%m/%d}/{run_id}'
    key = base + '.dump'
    # Only the completed manifest marks this run as successful.
    client.upload_file(str(path), bucket, key, ExtraArgs={
        'ServerSideEncryption': 'AES256',
        'Metadata': {'sha256': checksum},
    })
    manifest = {
        'format': 'pg_dump-custom', 'started_at': started,
        'uploaded_at': datetime.now(timezone.utc).isoformat(), 'archive_key': key,
        'size_bytes': path.stat().st_size, 'sha256': checksum,
    }
    client.put_object(Bucket=bucket, Key=base + '.json',
                      Body=json.dumps(manifest).encode(),
                      ContentType='application/json', ServerSideEncryption='AES256')
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true',
                        help='Validate configuration only; no database or AWS calls.')
    args = parser.parse_args()
    try:
        env, bucket, region, prefix = settings()
        if args.dry_run:
            print('Configuration valid. No DB connection, dump, upload, or credential check performed.')
            return 0
        import boto3
        from botocore.config import Config
        started = datetime.now(timezone.utc).isoformat()
        client = boto3.client('s3', region_name=region,
                              config=Config(connect_timeout=10, read_timeout=60,
                                            retries={'max_attempts': 3, 'mode': 'standard'}))
        with tempfile.TemporaryDirectory(prefix='skillissue-backup-') as directory:
            path = Path(directory) / 'database.dump'
            create_archive(path, env)
            manifest = upload_archive(client, path, bucket, prefix, started)
        print(json.dumps({'status': 'backup_uploaded', 'archive_key': manifest['archive_key'],
                          'size_bytes': manifest['size_bytes'], 'sha256': manifest['sha256']}))
        return 0
    except BackupError as error:
        print(f'Backup failed: {error}', file=sys.stderr)
    except Exception:
        print('Backup failed: upload, credential or runtime error. No completed backup confirmed.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
