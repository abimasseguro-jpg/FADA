"""FADA library boundary tests for the opt-in MVSNC adaptive policy."""
import unittest

from fada.adaptive import AdaptiveConfig, AdaptiveWatchdog
from fada.dispatcher import FADADispatcher
from fada.domain import WorkerSlot


class AdaptiveBoundaryTests(unittest.TestCase):
    def test_plan_is_pure_and_dispatch_remains_separate(self):
        tasks = [f"d{d:02d}_i01_r001" for d in (1, 2, 3)]
        workers = [WorkerSlot(f"w:{i}", "w", speed=1) for i in range(3)]
        pending = list(tasks)
        active = {}
        completed = []
        watchdog = AdaptiveWatchdog(AdaptiveConfig())
        planned = FADADispatcher.plan_adaptive(pending, active, completed,
                                                workers, workers, watchdog, now=100)
        self.assertEqual(len(planned), 3)
        self.assertEqual(pending, tasks)
        self.assertEqual(active, {})
        self.assertEqual({task for task, _ in planned}, set(tasks))

    def test_bad_persisted_state_is_rejected(self):
        with self.assertRaises(ValueError):
            AdaptiveWatchdog(AdaptiveConfig(), {"schema": "other", "phase": "RECOVERY"})
        with self.assertRaises(ValueError):
            AdaptiveWatchdog(AdaptiveConfig(), {"phase": "RECOVERY", "targets": {1: -1}})


if __name__ == "__main__":
    unittest.main()
