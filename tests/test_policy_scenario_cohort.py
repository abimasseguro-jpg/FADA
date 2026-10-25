import unittest

from fada.dispatcher import FADADispatcher
from fada.domain import Task, WorkerSlot
from fada.estimation import ScenarioEstimator
from fada.policy_scenario_cohort import (
    ConcurrentScenarioPolicy, CostBalancedScenarioPolicy,
    ScenarioStatus, ScenarioWorkStatus,
)


class Queue:
    def __init__(self):
        self.claims = []

    def claim(self, task_id, worker_id, key):
        self.claims.append((task_id, worker_id, key))
        return True


class ConcurrentScenarioTests(unittest.TestCase):
    def setUp(self):
        self.estimator = ScenarioEstimator(minimum_samples=1)
        self.estimator.extend([(s, "host", 1.0) for s in ("n100", "n200", "n400")])
        self.workers = [WorkerSlot(f"w{i}", "host") for i in range(3)]
        self.tasks = [Task(f"{s}-{i}", s) for s in ("n100", "n200", "n400") for i in range(3)]

    def test_three_successive_claims_start_all_scenarios(self):
        dispatcher = FADADispatcher(policy=ConcurrentScenarioPolicy())
        queue = Queue()
        pending = list(self.tasks)
        status = {s: ScenarioStatus(0, 0) for s in ("n100", "n200", "n400")}
        chosen = []
        for worker in self.workers:
            receipt = dispatcher.dispatch(pending, [worker], self.estimator, queue,
                                          scenario_status=status)
            self.assertTrue(receipt.claimed)
            task = next(t for t in pending if t.task_id == receipt.decision.task_id)
            chosen.append(task.scenario)
            pending.remove(task)
            old = status[task.scenario]
            status[task.scenario] = ScenarioStatus(old.completed, old.active + 1)
        self.assertEqual(chosen, ["n100", "n200", "n400"])
        self.assertEqual(len(queue.claims), 3)

    def test_completed_fraction_rebalances_subsequent_claim(self):
        policy = ConcurrentScenarioPolicy()
        decision = policy.choose(self.tasks, self.workers, self.estimator,
                                 scenario_status={"n100": ScenarioStatus(2, 0),
                                                  "n200": ScenarioStatus(0, 0),
                                                  "n400": ScenarioStatus(1, 0)})
        self.assertEqual(decision.action, "dispatch")
        self.assertTrue(decision.task_id.startswith("n200"))

    def test_missing_status_fails_without_claim(self):
        queue = Queue()
        receipt = FADADispatcher(policy=ConcurrentScenarioPolicy()).dispatch(
            self.tasks, self.workers, self.estimator, queue,
            scenario_status={"n100": ScenarioStatus(0, 0)})
        self.assertEqual(receipt.decision.reason, "scenario_status_mismatch")
        self.assertFalse(receipt.claimed)
        self.assertEqual(queue.claims, [])

    def test_ineligible_scenario_does_not_block_others(self):
        tasks = [Task("a", "n100", eligible_workers=frozenset({"other"})),
                 Task("b", "n200")]
        decision = ConcurrentScenarioPolicy().choose(
            tasks, [self.workers[0]], self.estimator,
            scenario_status={"n100": ScenarioStatus(0, 0),
                             "n200": ScenarioStatus(1, 0)})
        self.assertEqual(decision.task_id, "b")


class CostBalancedScenarioTests(unittest.TestCase):
    def setUp(self):
        self.estimator = ScenarioEstimator(cold_start_seconds=10.0, minimum_samples=1)
        self.workers = [WorkerSlot("slow", "slow", speed=1.0),
                        WorkerSlot("fast", "fast", speed=4.0)]

    def test_selects_least_advanced_work_not_smallest_task_count(self):
        tasks = [Task("cheap-1", "cheap", complexity=1.0),
                 Task("expensive-1", "expensive", complexity=10.0)]
        status = {
            "cheap": ScenarioWorkStatus(completed_work=8.0, active_work=0.0),
            "expensive": ScenarioWorkStatus(completed_work=1.0, active_work=0.0),
        }
        decision = CostBalancedScenarioPolicy().choose(
            tasks, self.workers, self.estimator, scenario_status=status)
        self.assertEqual(decision.action, "dispatch")
        self.assertEqual(decision.task_id, "expensive-1")
        self.assertIn("cost_balanced_scenario:expensive", decision.reason)

    def test_costly_task_is_mapped_to_fast_worker(self):
        tasks = [Task("light", "same", complexity=1.0),
                 Task("heavy", "same", complexity=10.0)]
        decision = CostBalancedScenarioPolicy().choose(
            tasks, self.workers, self.estimator,
            scenario_status={"same": ScenarioWorkStatus(0.0, 0.0)})
        self.assertEqual(decision.action, "dispatch")
        self.assertEqual(decision.task_id, "heavy")
        self.assertEqual(decision.worker_id, "fast")

    def test_missing_work_snapshot_fails_closed(self):
        decision = CostBalancedScenarioPolicy().choose(
            [Task("one", "a")], self.workers, self.estimator,
            scenario_status=None)
        self.assertEqual(decision.action, "fallback")
        self.assertEqual(decision.reason, "scenario_work_status_mismatch")


if __name__ == "__main__":
    unittest.main()
