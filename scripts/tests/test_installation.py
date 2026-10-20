import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('doctor', SCRIPTS / 'doctor.py')
doctor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)


class InstallationTests(unittest.TestCase):
    def test_missing_gpu_is_an_error_before_installation(self):
        with patch.object(doctor.platform, 'system', return_value='Linux'), \
             patch.object(doctor.platform, 'machine', return_value='x86_64'), \
             patch.object(doctor.shutil, 'which', return_value=None), \
             patch.object(doctor.Path, 'is_file', return_value=False), \
             patch.object(doctor, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'NVIDIA GPU not visible'):
                doctor.preflight('gpu')
            run.assert_not_called()

    def test_remote_preflight_does_not_probe_gpu(self):
        with patch.object(doctor.platform, 'system', return_value='Linux'), \
             patch.object(doctor.platform, 'machine', return_value='x86_64'), \
             patch.object(doctor, 'run') as run:
            doctor.preflight('remote')
            run.assert_not_called()

    def test_old_driver_rejected(self):
        with patch.object(doctor.platform, 'system', return_value='Linux'), \
             patch.object(doctor.platform, 'machine', return_value='x86_64'), \
             patch.object(doctor.shutil, 'which', return_value='nvidia-smi'), \
             patch.object(doctor, 'run', return_value='550.90.07'):
            with self.assertRaisesRegex(RuntimeError, '560'):
                doctor.preflight('gpu')

    def test_snapshot_marker_and_weights_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'scripts').mkdir()
            (root / 'scripts/model-catalog.json').write_text(json.dumps({'models': [
                {'id': 'fixture/model', 'revision': 'immutable', 'profile': 'default'}]}))
            directory = root / 'models/fixture__model'
            directory.mkdir(parents=True)
            with patch.object(doctor, 'ROOT', root):
                with self.assertRaisesRegex(RuntimeError, 'incomplete'):
                    doctor.check_models()
                (directory / '.meetsift-revision').write_text('immutable')
                with self.assertRaisesRegex(RuntimeError, 'weights'):
                    doctor.check_models()
                (directory / 'config.json').write_text('{}')
                (directory / 'model.safetensors').write_bytes(b'fixture')
                self.assertEqual(doctor.check_models(), [directory])

    def test_token_rerun_preserves_existing_secret_and_permissions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'scripts').mkdir()
            script = root / 'scripts/init-local.py'
            shutil.copyfile(SCRIPTS / 'init-local.py', script)
            first = subprocess.run([sys.executable, script], capture_output=True)
            self.assertEqual(first.returncode, 0)
            token = root / '.local-data/api-token'
            original = token.read_bytes()
            second = subprocess.run([sys.executable, script], capture_output=True)
            self.assertEqual(second.returncode, 0)
            self.assertEqual(token.read_bytes(), original)
            self.assertNotIn(original, first.stdout + first.stderr + second.stdout + second.stderr)
            if sys.platform != 'win32':
                self.assertEqual(token.stat().st_mode & 0o777, 0o600)

    def test_invalid_existing_token_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'scripts').mkdir()
            (root / '.local-data').mkdir()
            script = root / 'scripts/init-local.py'
            shutil.copyfile(SCRIPTS / 'init-local.py', script)
            token = root / '.local-data/api-token'
            token.write_text('invalid-fixture')
            result = subprocess.run([sys.executable, script], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(token.read_text(), 'invalid-fixture')


if __name__ == '__main__':
    unittest.main()
