import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fada.concurrency import ConcurrencySample, ObservedConcurrencyCurve


class ObservedConcurrencyCurveTests(unittest.TestCase):
    def _sample(self, identity: str, workers: int, tasks: int, elapsed: float, **changes):
        values = {
            "observation_id": identity, "machine_id": "server", "backend": "cpu",
            "hardware_profile": "xeon", "active_workers": workers, "completed_tasks": tasks,
            "elapsed_seconds": elapsed, "observed_at": 1.0,
        }
        values.update(changes)
        return ConcurrencySample(**values)

    def test_only_observed_levels_are_estimable(self) -> None:
        curve = ObservedConcurrencyCurve(minimum_samples_per_level=2)
        curve.observe(self._sample("one", 2, 20, 10.0))
        curve.observe(self._sample("two", 2, 24, 10.0))
        estimate = curve.estimate(machine_id="server", backend="cpu", hardware_profile="xeon", active_workers=2)
        self.assertIsNotNone(estimate)
        self.assertIsNone(curve.estimate(machine_id="server", backend="cpu", hardware_profile="xeon", active_workers=4))

    def test_best_observed_level_is_not_automatically_the_largest(self) -> None:
        curve = ObservedConcurrencyCurve(minimum_samples_per_level=2)
        for identity, workers, tasks, elapsed in (
            ("a", 2, 20, 10.0), ("b", 2, 22, 10.0),
            ("c", 4, 20, 10.0), ("d", 4, 21, 10.0),
        ):
            curve.observe(self._sample(identity, workers, tasks, elapsed))
        self.assertEqual(curve.best_observed_workers(machine_id="server", backend="cpu", hardware_profile="xeon"), 2)

    def test_duplicate_identity_and_incompatible_backend_fail_closed(self) -> None:
        curve = ObservedConcurrencyCurve()
        item = self._sample("same", 2, 20, 10.0)
        curve.observe(item)
        with self.assertRaises(ValueError):
            curve.observe(item)
        self.assertIsNone(curve.estimate(machine_id="server", backend="cuda", hardware_profile="xeon", active_workers=2))
