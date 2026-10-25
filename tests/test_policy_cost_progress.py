import unittest

from fada.domain import Task, WorkerSlot
from fada.estimation import ScenarioEstimator
from fada.policy_cost_progress import CostWeightedProgressPolicy


class CostWeightedProgressPolicyTests(unittest.TestCase):
    def setUp(self):
        self.workers = [WorkerSlot("w1", "fast", speed=1.0)]
        self.estimator = ScenarioEstimator(minimum_samples=1)
        self.estimator.extend([
            ("cheap", "fast", 1.0),
            ("expensive", "fast", 10.0),
        ])
        self.tasks = [
            Task("c1", "cheap"), Task("c2", "cheap"),
            Task("e1", "expensive"), Task("e2", "expensive"),
        ]

    def test_internal_progress_changes_selected_scenario(self):
        policy = CostWeightedProgressPolicy()
        decision = policy.choose(
            self.tasks, self.workers, self.estimator,
            progress={"c1": 0.9, "c2": 0.9, "e1": 0.1, "e2": 0.1},
        )
        self.assertEqual(decision.action, "dispatch")
        self.assertIn(decision.task_id, {"e1", "e2"})
        self.assertIn("cost_weighted_progress_fair_share", decision.reason)

    def test_missing_or_invalid_progress_fails_closed(self):
        policy = CostWeightedProgressPolicy()
        missing = policy.choose(self.tasks, self.workers, self.estimator)
        self.assertEqual(missing.action, "fallback")
        invalid = policy.choose(
            self.tasks, self.workers, self.estimator,
            progress={task.task_id: 2.0 for task in self.tasks},
        )
        self.assertEqual(invalid.action, "fallback")

    def test_invalid_cost_fails_closed(self):
        policy = CostWeightedProgressPolicy()
        estimator = ScenarioEstimator(minimum_samples=1)
        estimator.observe("cheap", "fast", 0.0) if False else None
        decision = policy.choose(
            self.tasks, self.workers, estimator,
            progress={task.task_id: 0.0 for task in self.tasks},
        )
        self.assertEqual(decision.action, "fallback")


if __name__ == "__main__":
    unittest.main()
