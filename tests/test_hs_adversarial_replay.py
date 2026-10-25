from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from run_hs_adversarial_replay import replay


class HsAdversarialReplayTests(unittest.TestCase):
    def test_replay_is_deterministic_and_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = replay("tail", 700, Path(directory) / "one.jsonl")
            second = replay("tail", 700, Path(directory) / "two.jsonl")
        self.assertTrue(first["read_only"])
        self.assertTrue(first["unique_decision_ids"])
        self.assertEqual(first["ledger_sha256"], second["ledger_sha256"])


if __name__ == "__main__":
    unittest.main()
