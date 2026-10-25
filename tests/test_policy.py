from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fada import BoundedPlanGuardedHybridPolicy, GuardedHybridPolicy, HybridPolicy, PlanGuardedHybridPolicy, PolicyController, ScenarioEstimator, Task, WorkerSlot


class HybridPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.estimator = ScenarioEstimator(cold_start_seconds=10, minimum_samples=2)
        self.workers = [
            WorkerSlot("fast-0", "fast", speed=2),
            WorkerSlot("slow-0", "slow", speed=1),
        ]

    def test_long_task_is_dispatched_to_fast_slot(self) -> None:
        decision = HybridPolicy().choose(
            [Task("long", "large", complexity=10), Task("short", "small")],
            self.workers,
            self.estimator,
        )
        self.assertEqual((decision.action, decision.task_id, decision.worker_id),
                         ("dispatch", "long", "fast-0"))

    def test_eligibility_is_respected(self) -> None:
        task = Task("restricted", "large", eligible_workers=frozenset({"slow-0"}))
        decision = HybridPolicy().choose([task], self.workers, self.estimator)
        self.assertEqual(decision.worker_id, "slow-0")

    def test_missing_estimates_requests_safe_fallback(self) -> None:
        estimator = ScenarioEstimator()
        decision = HybridPolicy().choose([Task("x", "new")], self.workers, estimator)
        self.assertEqual((decision.action, decision.reason),
                         ("fallback", "insufficient_estimates"))

    def test_partial_estimate_coverage_requests_safe_fallback(self) -> None:
        estimator = ScenarioEstimator()
        estimator.observe("known", "fast", 5)
        decision = HybridPolicy().choose(
            [Task("known", "known"), Task("unknown", "unknown")],
            self.workers,
            estimator,
        )
        self.assertEqual((decision.action, decision.reason),
                         ("fallback", "partial_estimate_coverage"))

    def test_wait_is_explicit_and_margin_guarded(self) -> None:
        decision = HybridPolicy(epsilon_seconds=2).choose(
            [Task("x", "scenario")], self.workers, self.estimator,
            wait_objective=4,
        )
        self.assertEqual(decision.action, "wait")

    def test_wait_gain_inside_margin_dispatches_now(self) -> None:
        decision = HybridPolicy(epsilon_seconds=2).choose(
            [Task("x", "scenario")], self.workers, self.estimator,
            wait_objective=8,
        )
        self.assertEqual(decision.action, "dispatch")

    def test_disabled_worker_is_never_selected(self) -> None:
        workers = [
            WorkerSlot("disabled", "fast", speed=100, enabled=False),
            WorkerSlot("enabled", "slow", speed=1),
        ]
        decision = HybridPolicy().choose(
            [Task("x", "scenario")], workers, self.estimator
        )
        self.assertEqual((decision.action, decision.worker_id), ("dispatch", "enabled"))

    def test_pool_without_enabled_worker_requests_fallback(self) -> None:
        decision = HybridPolicy().choose(
            [Task("x", "scenario")],
            [WorkerSlot("disabled", "fast", enabled=False)],
            self.estimator,
        )
        self.assertEqual(
            (decision.action, decision.reason),
            ("fallback", "empty_queue_or_pool"),
        )

    def test_tie_is_deterministic(self) -> None:
        workers = [WorkerSlot("b", "same"), WorkerSlot("a", "same")]
        tasks = [Task("b", "same"), Task("a", "same")]
        decision = HybridPolicy().choose(tasks, workers, self.estimator)
        self.assertEqual((decision.task_id, decision.worker_id), ("a", "a"))

    def test_adverse_tail_keeps_long_task_on_fast_slot(self) -> None:
        tasks = [Task("long", "tail", complexity=50)] + [
            Task(f"short-{index:02d}", "tail") for index in range(20)
        ]
        decision = HybridPolicy(candidate_window=8, projection_limit=8).choose(
            tasks, self.workers, self.estimator
        )
        self.assertEqual((decision.task_id, decision.worker_id), ("long", "fast-0"))

    def test_duplicate_identifiers_request_fallback(self) -> None:
        duplicate_tasks = [Task("same", "x"), Task("same", "x")]
        task_decision = HybridPolicy().choose(
            duplicate_tasks, self.workers, self.estimator
        )
        duplicate_workers = [WorkerSlot("same", "a"), WorkerSlot("same", "b")]
        worker_decision = HybridPolicy().choose(
            [Task("x", "x")], duplicate_workers, self.estimator
        )
        self.assertEqual(task_decision.reason, "duplicate_task_id")
        self.assertEqual(worker_decision.reason, "duplicate_worker_id")

    def test_policy_configuration_rejects_invalid_bounds(self) -> None:
        for arguments in (
            {"candidate_window": 0},
            {"projection_limit": -1},
            {"uncertainty_weight": -0.1},
            {"epsilon_seconds": -1},
            {"version": ""},
        ):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                HybridPolicy(**arguments)

    def test_version_is_recorded_and_rollback_is_reversible(self) -> None:
        original = HybridPolicy(version="fada-hs/0.1")
        controller = PolicyController(original)
        promoted = HybridPolicy(version="fada-hs/0.2", uncertainty_weight=0.5)
        controller.promote(promoted)
        decision = controller.active.choose(
            [Task("x", "scenario")], self.workers, self.estimator
        )
        self.assertEqual(decision.policy_version, "fada-hs/0.2")
        self.assertIs(controller.rollback(), original)
        self.assertEqual(controller.active.version, "fada-hs/0.1")

    def test_rollback_without_previous_policy_fails_explicitly(self) -> None:
        controller = PolicyController(HybridPolicy())
        with self.assertRaises(RuntimeError):
            controller.rollback()

    def test_v02_preserves_sufferage_when_candidate_advantage_is_inconclusive(self) -> None:
        decision = GuardedHybridPolicy(safety_margin_fraction=0.9).choose(
            [Task("a", "scenario"), Task("b", "scenario")], self.workers, self.estimator
        )
        self.assertEqual((decision.policy_version, decision.reason), ("fada-hs/0.2", "sufferage_baseline_guard"))

    def test_v02_fails_closed_without_baseline_coverage(self) -> None:
        decision = GuardedHybridPolicy().choose(
            [Task("x", "unknown")], self.workers, ScenarioEstimator()
        )
        self.assertEqual((decision.action, decision.reason), ("fallback", "baseline_insufficient_estimates"))

    def test_v03_keeps_sufferage_when_whole_plan_has_no_margin(self) -> None:
        decision = PlanGuardedHybridPolicy(plan_safety_margin_fraction=0.02).choose(
            [Task("a", "scenario"), Task("b", "scenario")], self.workers, self.estimator
        )
        self.assertEqual((decision.policy_version, decision.reason), ("fada-hs/0.3", "sufferage_whole_plan_guard"))

    def test_v03_fails_closed_without_baseline_coverage(self) -> None:
        decision = PlanGuardedHybridPolicy().choose(
            [Task("x", "unknown")], self.workers, ScenarioEstimator()
        )
        self.assertEqual((decision.action, decision.reason), ("fallback", "baseline_insufficient_estimates"))

    def test_v04_keeps_v03_guard_with_bounded_projection(self) -> None:
        policy = BoundedPlanGuardedHybridPolicy()
        decision = policy.choose([Task("a", "scenario")], self.workers, self.estimator)
        self.assertEqual((policy.version, policy.candidate_window, policy.projection_limit), ("fada-hs/0.4", 8, 24))
        self.assertIn(decision.reason, {"sufferage_whole_plan_guard", "fada_candidate_beats_sufferage_whole_plan"})


if __name__ == "__main__":
    unittest.main()
