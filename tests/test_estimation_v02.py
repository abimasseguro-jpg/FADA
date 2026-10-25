import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fada import DurationObservation, ExecutionOutcome
from fada.estimation_v02 import EstimatorContext, StratifiedDurationEstimator


class StratifiedDurationEstimatorTests(unittest.TestCase):
    def _observation(self, identity: str, *, machine="a", backend="cpu", hardware="xeon", outcome=ExecutionOutcome.COMPLETED, elapsed=10.0, observed_at=1.0, **extra):
        return DurationObservation(
            observation_id=identity, scenario="n100", machine_id=machine, backend=backend,
            hardware_profile=hardware, active_workers=2, observed_at=observed_at,
            outcome=outcome, elapsed_seconds=elapsed, **extra,
        )

    def _context(self, **changes):
        values = {"scenario": "n100", "machine_id": "a", "backend": "cpu", "hardware_profile": "xeon"}
        values.update(changes)
        return EstimatorContext(**values)

    def test_completed_exact_observations_produce_ordered_estimate(self) -> None:
        estimator = StratifiedDurationEstimator(minimum_samples=3)
        for identity, elapsed in (("one", 8.0), ("two", 10.0), ("three", 20.0)):
            estimator.observe(self._observation(identity, elapsed=elapsed))
        estimate = estimator.estimate(self._context())
        self.assertIsNotNone(estimate)
        assert estimate is not None
        self.assertEqual(estimate.source, "exact")
        self.assertEqual(estimate.point_seconds, 10.0)
        self.assertLessEqual(estimate.lower_seconds, estimate.p50_seconds)
        self.assertLessEqual(estimate.p95_seconds, estimate.upper_seconds)

    def test_censor_failure_and_incompatible_context_never_become_duration_samples(self) -> None:
        estimator = StratifiedDurationEstimator()
        estimator.observe(self._observation("censored", outcome=ExecutionOutcome.CENSORED, elapsed=5.0, censor_limit_seconds=6.0, reason="limit"))
        estimator.observe(self._observation("failed", outcome=ExecutionOutcome.FAILED, elapsed=2.0, reason="error"))
        estimator.observe(self._observation("gpu", backend="cuda", elapsed=99.0))
        estimator.observe(self._observation("other-hardware", hardware="epyc", elapsed=88.0))
        self.assertIsNone(estimator.estimate(self._context()))

    def test_only_machine_identity_can_fallback_within_compatible_stratum(self) -> None:
        estimator = StratifiedDurationEstimator(minimum_samples=2)
        estimator.observe(self._observation("one", machine="b", elapsed=12.0))
        estimator.observe(self._observation("two", machine="b", elapsed=14.0))
        estimate = estimator.estimate(self._context())
        self.assertIsNotNone(estimate)
        assert estimate is not None
        self.assertEqual(estimate.source, "compatible_hardware_fallback")
        self.assertEqual(estimate.confidence, 0.5)

    def test_duplicate_observation_identity_fails_closed(self) -> None:
        estimator = StratifiedDurationEstimator()
        estimator.observe(self._observation("same"))
        with self.assertRaises(ValueError):
            estimator.observe(self._observation("same", elapsed=11.0))

    def test_stationary_trace_does_not_trigger_drift(self) -> None:
        estimator = StratifiedDurationEstimator(drift_minimum_samples=2, drift_window_seconds=20.0)
        for index, elapsed in enumerate((10.0, 11.0, 10.0, 11.0)):
            estimator.observe(self._observation(f"stable-{index}", elapsed=elapsed, observed_at=float(index + 1)))
        estimate = estimator.estimate(self._context(), now=5.0)
        self.assertIsNotNone(estimate)
        assert estimate is not None
        self.assertFalse(estimate.drift_detected)

    def test_known_temporal_shift_selects_recent_regime(self) -> None:
        estimator = StratifiedDurationEstimator(
            drift_minimum_samples=2, drift_window_seconds=20.0, drift_ratio_threshold=1.5,
        )
        for index, elapsed in enumerate((10.0, 11.0, 20.0, 22.0)):
            estimator.observe(self._observation(f"drift-{index}", elapsed=elapsed, observed_at=float(index + 1)))
        estimate = estimator.estimate(self._context(), now=5.0)
        self.assertIsNotNone(estimate)
        assert estimate is not None
        self.assertTrue(estimate.drift_detected)
        self.assertEqual(estimate.regime_started_at, 3.0)
        self.assertGreaterEqual(estimate.point_seconds, 20.0)
