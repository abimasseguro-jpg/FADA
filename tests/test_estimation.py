from __future__ import annotations

import unittest

from fada import ScenarioEstimator, Task, WorkerSlot


class ScenarioEstimatorTests(unittest.TestCase):
    def test_direct_estimate_uses_median_and_sample_confidence(self) -> None:
        estimator = ScenarioEstimator(minimum_samples=4)
        estimator.extend([("s", "m", 9), ("s", "m", 11), ("s", "m", 100)])
        estimate = estimator.estimate(Task("x", "s", complexity=2), WorkerSlot("w", "m"))
        self.assertEqual(estimate, (22, 0.75))

    def test_scenario_fallback_adjusts_for_worker_speed(self) -> None:
        estimator = ScenarioEstimator()
        estimator.observe("s", "observed", 20)
        estimate = estimator.estimate(Task("x", "s"), WorkerSlot("w", "new", speed=2))
        self.assertEqual(estimate, (10, 0.4))

    def test_cold_start_is_explicit_and_low_confidence(self) -> None:
        estimator = ScenarioEstimator(cold_start_seconds=30)
        estimate = estimator.estimate(
            Task("x", "unknown", complexity=2), WorkerSlot("w", "new", speed=3)
        )
        self.assertEqual(estimate, (20, 0.15))

    def test_absent_prior_returns_no_estimate(self) -> None:
        self.assertIsNone(
            ScenarioEstimator().estimate(Task("x", "unknown"), WorkerSlot("w", "m"))
        )

    def test_invalid_observation_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ScenarioEstimator().observe("s", "m", 0)


if __name__ == "__main__":
    unittest.main()
