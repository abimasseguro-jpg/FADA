from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from backtest_temporal import POLICIES, build_trace, run_backtest, schedule


class TemporalBacktestTests(unittest.TestCase):
    def test_all_policies_schedule_the_same_complete_trace(self) -> None:
        trace = build_trace(7, tasks_per_scenario=2)
        for policy in POLICIES:
            with self.subTest(policy=policy):
                metrics = schedule(trace, policy)
                self.assertGreater(metrics.makespan, 0)
                self.assertGreaterEqual(metrics.idle_fraction, 0)
                self.assertLess(metrics.idle_fraction, 1)

    def test_backtest_is_reproducible_except_for_timing_metrics(self) -> None:
        first = run_backtest(replicates=3, tasks_per_scenario=2, bootstrap_samples=50)
        second = run_backtest(replicates=3, tasks_per_scenario=2, bootstrap_samples=50)
        self.assertEqual(first["replicates"], second["replicates"])
        self.assertEqual(
            first["noninferiority"]["paired_mean_regression_upper_95"],
            second["noninferiority"]["paired_mean_regression_upper_95"],
        )
        for policy in POLICIES:
            self.assertEqual(
                first["policies"][policy]["makespan_mean"],
                second["policies"][policy]["makespan_mean"],
            )

    def test_invalid_backtest_size_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            run_backtest(replicates=1, tasks_per_scenario=1, bootstrap_samples=10)
        with self.assertRaises(ValueError):
            run_backtest(replicates=2, tasks_per_scenario=1, bootstrap_samples=10, seed_start=-1)

    def test_parallel_results_preserve_deterministic_outcomes(self) -> None:
        sequential = run_backtest(replicates=4, tasks_per_scenario=2, bootstrap_samples=50, seed_start=100)
        parallel = run_backtest(replicates=4, tasks_per_scenario=2, bootstrap_samples=50, max_workers=2, seed_start=100)
        self.assertEqual(sequential["noninferiority"], parallel["noninferiority"])


if __name__ == "__main__":
    unittest.main()
