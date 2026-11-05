"""Restore an archive only into an explicitly selected empty test database."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from backup import BackupError, command, postgres_env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--confirm-empty-target', action='store_true')
    args = parser.parse_args()
    try:
        if not args.confirm_empty_target:
            raise BackupError('Explicit --confirm-empty-target is required.')
        target = postgres_env(os.environ.get('RESTORE_DATABASE_URL', ''))
        if os.environ.get('DATABASE_URL'):
            source = postgres_env(os.environ['DATABASE_URL'])
            identity = lambda env: (env['PGHOST'], env['PGPORT'], env['PGDATABASE'])
            if identity(target) == identity(source):
                raise BackupError('Restore target must differ from the source database.')
        manifest = json.loads(args.manifest.read_text())
        with args.archive.open('rb') as source:
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
        if digest != manifest['sha256'] or args.archive.stat().st_size != manifest['size_bytes']:
            raise BackupError('Archive checksum or size mismatch.')
        command(['pg_restore', '--list', str(args.archive)], target)
        sql = "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema'"
        check = subprocess.run(['psql', '--no-password', '-X', '-A', '-t', '-v',
                                'ON_ERROR_STOP=1', '-c', sql], env=target,
                               capture_output=True, timeout=60)
        if check.returncode != 0 or check.stdout.strip() != b'0':
            raise BackupError('Target is not empty or cannot be checked. No restore performed.')
        command(['pg_restore', '--no-password', '--exit-on-error', '--single-transaction',
                 '--no-owner', '--no-acl', '--dbname', target['PGDATABASE'], str(args.archive)], target)
        command(['psql', '--no-password', '-X', '-v', 'ON_ERROR_STOP=1', '-c',
                 'SELECT count(*) FROM public.submissions;'], target)
        print('Restore succeeded in the selected empty test database; submissions is readable.')
        return 0
    except BackupError as error:
        print(f'Restore verification failed: {error}', file=sys.stderr)
    except Exception:
        print('Restore verification failed. Check the files, test DB, TLS and client tools.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
