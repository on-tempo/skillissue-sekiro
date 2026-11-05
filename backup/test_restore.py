import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import restore_verify


class RestoreTests(unittest.TestCase):
    def test_requires_explicit_confirmation(self):
        with patch('sys.argv', ['restore_verify.py', 'a.dump', 'a.json']), patch('restore_verify.command') as command:
            self.assertEqual(restore_verify.main(), 1)
            command.assert_not_called()

    def test_refuses_source_as_target(self):
        url = 'postgresql://user:pass@source.example/game'
        with patch.dict(os.environ, {'DATABASE_URL': url, 'RESTORE_DATABASE_URL': url}), patch('sys.argv', ['restore_verify.py', 'a.dump', 'a.json', '--confirm-empty-target']), patch('restore_verify.command') as command:
            self.assertEqual(restore_verify.main(), 1)
            command.assert_not_called()

    def test_nonempty_target_does_not_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            dump = Path(directory) / 'a.dump'; dump.write_bytes(b'example')
            manifest = Path(directory) / 'a.json'
            manifest.write_text(json.dumps({'size_bytes': 7, 'sha256': hashlib.sha256(b'example').hexdigest()}))
            env = {'DATABASE_URL': 'postgresql://user:pass@source.example/game',
                   'RESTORE_DATABASE_URL': 'postgresql://user:pass@test.example/empty'}
            with patch.dict(os.environ, env), patch('sys.argv', ['restore_verify.py', str(dump), str(manifest), '--confirm-empty-target']), patch('restore_verify.command') as command, patch('restore_verify.subprocess.run', return_value=Mock(returncode=0, stdout=b'2')):
                self.assertEqual(restore_verify.main(), 1)
                self.assertEqual(command.call_count, 1)
                self.assertIn('--list', command.call_args.args[0])

    def test_checksum_failure_does_not_contact_db(self):
        with tempfile.TemporaryDirectory() as directory:
            dump = Path(directory) / 'a.dump'; dump.write_bytes(b'example')
            manifest = Path(directory) / 'a.json'; manifest.write_text(json.dumps({'size_bytes': 7, 'sha256': 'bad'}))
            env = {'DATABASE_URL': 'postgresql://user:pass@source.example/game',
                   'RESTORE_DATABASE_URL': 'postgresql://user:pass@test.example/empty'}
            with patch.dict(os.environ, env), patch('sys.argv', ['restore_verify.py', str(dump), str(manifest), '--confirm-empty-target']), patch('restore_verify.command') as command:
                self.assertEqual(restore_verify.main(), 1)
                command.assert_not_called()


if __name__ == '__main__':
    unittest.main()
