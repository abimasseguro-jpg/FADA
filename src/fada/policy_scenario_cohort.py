"""Keep scenarios advancing together when new worker slots become available."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

from .domain import Decision, Task, WorkerSlot
from .estimation import ScenarioEstimator
from .policy_v04 import BoundedPlanGuardedHybridPolicy


@dataclass(frozen=True, slots=True)
class ScenarioStatus:
    """Counts from one consistent queue snapshot, excluding pending tasks."""

    completed: int
    active: int

    def __post_init__(self) -> None:
        for value in (self.completed, self.active):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("scenario counts must be nonnegative integers")


@dataclass(frozen=True, slots=True)
class ScenarioWorkStatus:
    """Accepted and active work from one consistent scheduler snapshot."""

    completed_work: float
    active_work: float

    def __post_init__(self) -> None:
        for value in (self.completed_work, self.active_work):
            if not isinstance(value, (int, float)) or not isfinite(value) or value < 0:
                raise ValueError("scenario work must be finite and nonnegative")


@dataclass(slots=True)
class ConcurrentScenarioPolicy:
    """Select the least advanced eligible scenario before choosing a task/slot.

    A host supplies all pending tasks, free worker slots, and completed/active
    counts from the same snapshot. Active leases count as work already allocated
    so successive claims spread across scenarios. Existing queue ownership and
    retry order are never rewritten.
    """

    version: str = "fada-concurrent-scenarios/0.1"
    base_policy: BoundedPlanGuardedHybridPolicy | None = None

    def __post_init__(self) -> None:
        if self.base_policy is None:
            self.base_policy = BoundedPlanGuardedHybridPolicy()

    def choose(
        self,
        tasks: list[Task],
        workers: list[WorkerSlot],
        estimator: ScenarioEstimator,
        *,
        scenario_status: Mapping[str, ScenarioStatus] | None = None,
        now: float = 0.0,
    ) -> Decision:
        def fallback(reason: str) -> Decision:
            return Decision("fallback", None, None, None, 0.0, reason, self.version)

        active_workers = [worker for worker in workers if worker.enabled]
        if not tasks or not active_workers:
            return fallback("empty_queue_or_pool")
        if len({task.task_id for task in tasks}) != len(tasks):
            return fallback("duplicate_task_id")
        if len({worker.worker_id for worker in active_workers}) != len(active_workers):
            return fallback("duplicate_worker_id")
        pending_scenarios = {task.scenario for task in tasks}
        if scenario_status is None or set(scenario_status) != pending_scenarios:
            return fallback("scenario_status_mismatch")
        if any(not isinstance(value, ScenarioStatus) for value in scenario_status.values()):
            return fallback("invalid_scenario_status")

        pending_count = {scenario: 0 for scenario in pending_scenarios}
        dispatchable = set()
        eligible_ids = set()
        for task in tasks:
            pending_count[task.scenario] += 1
            if any(
                (not task.eligible_workers or worker.worker_id in task.eligible_workers)
                and estimator.estimate(task, worker) is not None
                for worker in active_workers
            ):
                dispatchable.add(task.scenario)
                eligible_ids.add(task.task_id)
        if not dispatchable:
            return fallback("no_dispatchable_scenario")

        def score(scenario: str) -> tuple[float, int, str]:
            state = scenario_status[scenario]
            total = state.completed + state.active + pending_count[scenario]
            fraction = (state.completed + state.active) / total
            return (fraction, state.active, scenario)

        scenario = min(dispatchable, key=score)
        candidates = [task for task in tasks if task.scenario == scenario and task.task_id in eligible_ids]
        assert self.base_policy is not None
        decision = self.base_policy.choose(candidates, active_workers, estimator, now=now)
        if decision.action != "dispatch":
            return fallback("selected_scenario_not_dispatchable")
        return Decision(
            "dispatch", decision.task_id, decision.worker_id,
            decision.projected_makespan, decision.confidence,
            f"concurrent_scenario:{scenario}", self.version,
        )


@dataclass(slots=True)
class CostBalancedScenarioPolicy:
    """Advance lagging work cohorts and map costly tasks to suitable workers."""

    version: str = "fada-cost-balanced-scenarios/0.1"
    base_policy: BoundedPlanGuardedHybridPolicy | None = None

    def __post_init__(self) -> None:
        if self.base_policy is None:
            self.base_policy = BoundedPlanGuardedHybridPolicy()

    def choose(self, tasks: list[Task], workers: list[WorkerSlot],
               estimator: ScenarioEstimator, *,
               scenario_status: Mapping[str, ScenarioWorkStatus] | None = None,
               now: float = 0.0) -> Decision:
        def fallback(reason: str) -> Decision:
            return Decision("fallback", None, None, None, 0.0, reason, self.version)

        active_workers = [worker for worker in workers if worker.enabled]
        if not tasks or not active_workers:
            return fallback("empty_queue_or_pool")
        if len({task.task_id for task in tasks}) != len(tasks):
            return fallback("duplicate_task_id")
        if len({worker.worker_id for worker in active_workers}) != len(active_workers):
            return fallback("duplicate_worker_id")
        scenarios = {task.scenario for task in tasks}
        if scenario_status is None or set(scenario_status) != scenarios:
            return fallback("scenario_work_status_mismatch")
        if any(not isinstance(value, ScenarioWorkStatus)
               for value in scenario_status.values()):
            return fallback("invalid_scenario_work_status")

        pending_work = {scenario: 0.0 for scenario in scenarios}
        dispatchable = set()
        for task in tasks:
            pending_work[task.scenario] += task.complexity
            if any((not task.eligible_workers or worker.worker_id in task.eligible_workers)
                   and estimator.estimate(task, worker) is not None
                   for worker in active_workers):
                dispatchable.add(task.scenario)
        if not dispatchable:
            return fallback("no_dispatchable_scenario")

        def score(scenario: str) -> tuple[float, float, str]:
            status = scenario_status[scenario]
            allocated = status.completed_work + status.active_work
            total = allocated + pending_work[scenario]
            return (allocated / total if total > 0 else 1.0,
                    status.active_work, scenario)

        scenario = min(dispatchable, key=score)
        candidates = [task for task in tasks if task.scenario == scenario]
        assert self.base_policy is not None
        decision = self.base_policy.choose(candidates, active_workers, estimator, now=now)
        if decision.action != "dispatch":
            return fallback("selected_scenario_not_dispatchable")
        return Decision(
            "dispatch", decision.task_id, decision.worker_id,
            decision.projected_makespan, decision.confidence,
            f"cost_balanced_scenario:{scenario}:work_fraction={score(scenario)[0]:.6f}",
            self.version,
        )
