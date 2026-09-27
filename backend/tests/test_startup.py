"""Check both supported Uvicorn import paths using the installed interpreter."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


class StartupTests(unittest.TestCase):
    def test_imports_from_root_and_backend(self):
        for cwd, module in [(ROOT, "backend.main"), (ROOT / "backend", "main")]:
            with self.subTest(module=module):
                result = subprocess.run(
                    [sys.executable, "-c", f"import importlib; m = importlib.import_module('{module}'); assert m.app; import uvicorn"],
                    cwd=cwd, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                    capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
