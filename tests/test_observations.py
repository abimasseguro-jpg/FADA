import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fada.observations import DurationObservation, ExecutionOutcome


class DurationObservationTests(unittest.TestCase):
    def _observation(self, **changes):
        values = {
            "observation_id": "obs-1", "scenario": "n100", "machine_id": "cpu-a",
            "backend": "cpu", "hardware_profile": "xeon-v4", "active_workers": 4,
            "observed_at": 12.0, "outcome": ExecutionOutcome.COMPLETED,
            "elapsed_seconds": 8.0,
        }
        values.update(changes)
        return DurationObservation(**values)

    def test_only_completed_runs_expose_a_training_duration(self) -> None:
        completed = self._observation()
        censored = self._observation(
            observation_id="obs-2", outcome=ExecutionOutcome.CENSORED,
            elapsed_seconds=8.0, censor_limit_seconds=10.0, reason="iteration_limit",
        )
        failed = self._observation(
            observation_id="obs-3", outcome=ExecutionOutcome.FAILED,
            elapsed_seconds=2.0, reason="runtime_error",
        )
        self.assertEqual(completed.completed_duration_seconds, 8.0)
        self.assertIsNone(censored.completed_duration_seconds)
        self.assertIsNone(failed.completed_duration_seconds)

    def test_invalid_outcome_metadata_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            self._observation(outcome=ExecutionOutcome.CENSORED, censor_limit_seconds=None)
        with self.assertRaises(ValueError):
            self._observation(outcome=ExecutionOutcome.FAILED, reason=None)
        with self.assertRaises(ValueError):
            self._observation(censor_limit_seconds=10.0)
        with self.assertRaises(ValueError):
            self._observation(active_workers=0)
