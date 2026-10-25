import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fada import DurationObservation, ExecutionOutcome, Task, WorkerSlot
from fada.estimation_v02 import StratifiedDurationEstimator
from fada.policy_estimator import PolicyEstimatorAdapter


class PolicyEstimatorAdapterTests(unittest.TestCase):
    def test_adapter_exposes_v02_estimate_without_mutating_policy_or_observation(self) -> None:
        estimator = StratifiedDurationEstimator()
        estimator.observe(DurationObservation(
            observation_id="one", scenario="n100", machine_id="fast", backend="cpu",
            hardware_profile="test", active_workers=1, observed_at=1.0,
            outcome=ExecutionOutcome.COMPLETED, elapsed_seconds=10.0,
        ))
        adapter = PolicyEstimatorAdapter(estimator, "cpu", "test")
        value = adapter.estimate(Task("task", "n100", complexity=2), WorkerSlot("slot", "fast"))
        self.assertEqual(value, (20.0, 1 / 3))
        self.assertEqual(len(estimator._observations), 1)

    def test_fixed_time_adapter_caches_without_changing_the_estimate(self) -> None:
        estimator = StratifiedDurationEstimator()
        estimator.observe(DurationObservation(
            observation_id="one", scenario="n100", machine_id="fast", backend="cpu",
            hardware_profile="test", active_workers=1, observed_at=1.0,
            outcome=ExecutionOutcome.COMPLETED, elapsed_seconds=10.0,
        ))
        adapter = PolicyEstimatorAdapter(estimator, "cpu", "test", now=2.0)
        task, worker = Task("task", "n100"), WorkerSlot("slot", "fast")
        self.assertEqual(adapter.estimate(task, worker), adapter.estimate(task, worker))
        self.assertEqual(len(adapter._cache), 1)
