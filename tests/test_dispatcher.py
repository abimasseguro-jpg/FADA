import unittest

from fada.dispatcher import FADADispatcher
from fada.domain import Task, WorkerSlot
from fada.estimation import ScenarioEstimator
from fada.policy_cost_progress import CostWeightedProgressPolicy
from fada.policy_scenario_cohort import CostBalancedScenarioPolicy, ScenarioWorkStatus


class Queue:
    def __init__(self):
        self.calls = []

    def claim(self, task_id, worker_id, idempotency_key):
        self.calls.append((task_id, worker_id, idempotency_key))
        return True


class DispatcherTests(unittest.TestCase):
    def test_active_claim_is_atomic_and_traceable(self):
        tasks = [Task("t1", "n75", complexity=1), Task("t2", "n125", complexity=2)]
        workers = [WorkerSlot("w1", "server27", speed=1), WorkerSlot("w2", "server27", speed=2)]
        est = ScenarioEstimator(minimum_samples=1)
        est.extend([("n75", "server27", 2), ("n125", "server27", 4)])
        q = Queue()
        receipt = FADADispatcher().dispatch(tasks, workers, est, q)
        self.assertEqual(receipt.decision.action, "dispatch")
        self.assertTrue(receipt.claimed)
        self.assertEqual(len(q.calls), 1)
        self.assertTrue(receipt.idempotency_key.startswith("fada-"))

    def test_fail_closed_without_estimates(self):
        q = Queue()
        receipt = FADADispatcher().dispatch(
            [Task("t1", "unknown")], [WorkerSlot("w1", "server27")],
            ScenarioEstimator(), q,
        )
        self.assertFalse(receipt.claimed)
        self.assertEqual(receipt.decision.action, "fallback")
        self.assertEqual(q.calls, [])

    def test_cost_progress_policy_is_opt_in_and_claims_only_selected_task(self):
        tasks = [Task("cheap", "cheap"), Task("expensive", "expensive")]
        workers = [WorkerSlot("w1", "server27")]
        est = ScenarioEstimator(minimum_samples=1)
        est.extend([("cheap", "server27", 1), ("expensive", "server27", 10)])
        q = Queue()
        receipt = FADADispatcher(policy=CostWeightedProgressPolicy()).dispatch(
            tasks, workers, est, q,
            progress={"cheap": 0.9, "expensive": 0.1},
        )
        self.assertEqual(receipt.decision.action, "dispatch")
        self.assertEqual(receipt.decision.task_id, "expensive")
        self.assertEqual([call[0] for call in q.calls], ["expensive"])

    def test_cost_balanced_scenario_policy_claims_selected_pair_atomically(self):
        tasks = [Task("light", "ahead", complexity=1),
                 Task("heavy", "behind", complexity=10)]
        workers = [WorkerSlot("slow", "slow", speed=1),
                   WorkerSlot("fast", "fast", speed=4)]
        estimator = ScenarioEstimator(cold_start_seconds=10, minimum_samples=1)
        queue = Queue()
        receipt = FADADispatcher(policy=CostBalancedScenarioPolicy()).dispatch(
            tasks, workers, estimator, queue,
            scenario_status={
                "ahead": ScenarioWorkStatus(9, 0),
                "behind": ScenarioWorkStatus(0, 0),
            },
        )
        self.assertTrue(receipt.claimed)
        self.assertEqual(receipt.decision.task_id, "heavy")
        self.assertEqual(receipt.decision.worker_id, "fast")
        self.assertEqual([(call[0], call[1]) for call in queue.calls],
                         [("heavy", "fast")])


if __name__ == "__main__":
    unittest.main()
