from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


class SentinelaFadaTests(unittest.TestCase):
    def test_deterministic_audit_contract(self) -> None:
        root = Path(__file__).resolve().parents[1]
        process = subprocess.run(
            [sys.executable, "governanca/tools/sentinela_fada.py", "audit",
             "--root", str(root), "--skip-tests"],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)


if __name__ == "__main__":
    unittest.main()

