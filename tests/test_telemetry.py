from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fada import DecisionLedgerEntry, append_entry, read_entries


class DecisionTelemetryTests(unittest.TestCase):
    def entry(self, sequence: int = 0) -> DecisionLedgerEntry:
        return DecisionLedgerEntry(
            decision_id=f"trace:{sequence}", trace_id="trace", sequence=sequence,
            policy_version="fada-hs/0.4", baseline_policy_version="sufferage/1",
            action="dispatch", task_id="task", worker_id="worker",
            baseline_task_id="task", baseline_worker_id="worker",
            reason="test", projected_makespan=1.0, baseline_projected_makespan=1.0,
            confidence=1.0, observed_elapsed_seconds=1.2,
        )

    def test_append_is_readable_and_observational(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            digest = append_entry(path, self.entry())
            self.assertEqual(len(digest), 64)
            self.assertEqual(read_entries(path)[0]["decision_id"], "trace:0")

    def test_reader_rejects_partial_or_duplicate_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            append_entry(path, self.entry())
            append_entry(path, self.entry())
            with self.assertRaises(ValueError):
                read_entries(path)
            path.write_bytes(b'{"partial": true}')
            with self.assertRaises(ValueError):
                read_entries(path)


if __name__ == "__main__":
    unittest.main()
