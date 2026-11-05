"""Offline checks: no real production DB or AWS credentials are used."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
import backup


class BackupTests(unittest.TestCase):
    def test_url_not_in_arguments_and_special_password(self):
        env = backup.postgres_env('postgresql://user:p%40ss%3Aword@db.example:5432/game?sslmode=require')
        self.assertEqual(env['PGPASSWORD'], 'p@ss:word')
        self.assertEqual(env['PGDATABASE'], 'game')
        with patch('backup.subprocess.run') as run:
            backup.command(['pg_dump', '--format=custom'], env)
            self.assertNotIn('p@ss:word', ' '.join(run.call_args.args[0]))

    def test_bad_url_and_plaintext_tls_rejected(self):
        for url in ['', 'sqlite:///data.db', 'postgresql://user:pass@host/db?sslmode=disable']:
            with self.subTest(url=url), self.assertRaises(backup.BackupError):
                backup.postgres_env(url)

    def test_environment_does_not_redirect_source(self):
        with patch.dict(os.environ, {'PGHOSTADDR': 'wrong-host', 'PGSERVICE': 'wrong-service'}):
            env = backup.postgres_env('postgresql://user:pass@db.example/game')
        self.assertNotIn('PGHOSTADDR', env)
        self.assertNotIn('PGSERVICE', env)

    def test_subprocess_secret_error_is_redacted(self):
        with patch('backup.subprocess.run', side_effect=subprocess.CalledProcessError(1, ['pg_dump'], stderr=b'PASSWORD-secret')):
            with self.assertRaises(backup.BackupError) as error:
                backup.command(['pg_dump'], {})
            self.assertNotIn('PASSWORD-secret', str(error.exception))

    def test_empty_dump_rejected_before_upload(self):
        with tempfile.TemporaryDirectory() as directory, patch('backup.command'):
            path = Path(directory) / 'test.dump'
            path.touch()
            with self.assertRaises(backup.BackupError):
                backup.create_archive(path, {})

    def test_archive_then_manifest_with_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.dump'
            path.write_bytes(b'archive-example')
            client = Mock()
            result = backup.upload_archive(client, path, 'example-bucket', 'postgres/', 'start')
            self.assertEqual(result['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertTrue(result['archive_key'].startswith('postgres/'))
            self.assertEqual([call[0] for call in client.method_calls], ['upload_file', 'put_object'])
            body = json.loads(client.put_object.call_args.kwargs['Body'])
            self.assertEqual(body, result)

    def test_no_completion_manifest_if_upload_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.dump'; path.write_bytes(b'data')
            client = Mock(); client.upload_file.side_effect = RuntimeError('failure')
            with self.assertRaises(RuntimeError):
                backup.upload_archive(client, path, 'example-bucket', 'postgres/', 'start')
            client.put_object.assert_not_called()

    def test_dry_run_uses_no_database_or_s3(self):
        env = {'DATABASE_URL': 'postgresql://user:pass@db.example/game',
               'BACKUP_S3_BUCKET': 'example-bucket', 'AWS_DEFAULT_REGION': 'us-east-1'}
        with patch.dict(os.environ, env), patch('sys.argv', ['backup.py', '--dry-run']), patch('backup.create_archive') as create:
            self.assertEqual(backup.main(), 0)
            create.assert_not_called()


if __name__ == '__main__':
    unittest.main()
