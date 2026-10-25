import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fada.calibration import DurationFeedback, calibrate_held_out
from fada.estimation_v02 import DurationEstimate


class CalibrationTests(unittest.TestCase):
    def _estimate(self):
        return DurationEstimate(
            point_seconds=10.0, p50_seconds=10.0, p95_seconds=15.0,
            lower_seconds=8.0, upper_seconds=15.0, confidence=1.0,
            sample_count=4, source="exact",
        )

    def _feedback(self, identity: str, elapsed: float, observed_at: float = 11.0):
        return DurationFeedback(identity, 10.0, observed_at, self._estimate(), elapsed)

    def test_held_out_metrics_include_coverage_eta_and_quantile_losses(self) -> None:
        metrics = calibrate_held_out([
            self._feedback("one", 10.0), self._feedback("two", 20.0, 12.0),
        ], evaluation_after=10.0)
        self.assertEqual(metrics.feedback_count, 2)
        self.assertEqual(metrics.interval_coverage, 0.5)
        self.assertGreater(metrics.mean_absolute_relative_error, 0.0)
        self.assertGreaterEqual(metrics.p50_pinball_loss, 0.0)
        self.assertGreaterEqual(metrics.p95_pinball_loss, 0.0)

    def test_non_held_out_or_duplicated_feedback_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            calibrate_held_out([self._feedback("old", 10.0, 10.0)], evaluation_after=10.0)
        duplicate = self._feedback("same", 10.0)
        with self.assertRaises(ValueError):
            calibrate_held_out([duplicate, duplicate], evaluation_after=10.0)
