"""Pure cost and internal-progress weighted FADA policy.

The policy only reads an immutable progress snapshot and returns an intent. It
never touches a queue, lease, campaign or result.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import median
from typing import Mapping

from .domain import Decision, Task, WorkerSlot
from .estimation import ScenarioEstimator
from .policy_v04 import BoundedPlanGuardedHybridPolicy


@dataclass(frozen=True, slots=True)
class ProgressSnapshot:
    """Normalized internal progress for one task, in the closed interval [0, 1]."""

    fraction: float

    def __post_init__(self) -> None:
        if not isfinite(self.fraction) or not 0.0 <= self.fraction <= 1.0:
            raise ValueError("progress fraction must be finite and in [0, 1]")


@dataclass(slots=True)
class CostWeightedProgressPolicy:
    """Select from the least advanced scenario by estimated work share.

    ``progress`` is required when this opt-in policy is used. Missing or
    invalid snapshot data fails closed. The existing guarded hybrid policy
    chooses the task and worker inside the selected scenario set.
    """

    version: str = "fada-cost-progress/0.1"
    base_policy: BoundedPlanGuardedHybridPolicy | None = None
    lease_reservation: float = 0.01
    requires_progress: bool = True

    def __post_init__(self) -> None:
        if not self.version:
            raise ValueError("policy version must not be empty")
        if not 0.0 < self.lease_reservation <= 1.0:
            raise ValueError("lease reservation must be in (0, 1]")
        if self.base_policy is None:
            self.base_policy = BoundedPlanGuardedHybridPolicy()

    @staticmethod
    def _eligible(task: Task, worker: WorkerSlot) -> bool:
        return worker.enabled and (
            not task.eligible_workers or worker.worker_id in task.eligible_workers
        )

    @staticmethod
    def _fallback(reason: str, policy_version: str) -> Decision:
        return Decision("fallback", None, None, None, 0.0, reason, policy_version)

    def _cost(
        self, task: Task, workers: list[WorkerSlot], estimator: ScenarioEstimator
    ) -> float | None:
        values: list[float] = []
        for worker in workers:
            if not self._eligible(task, worker):
                continue
            estimate = estimator.estimate(task, worker)
            if estimate is None:
                continue
            duration, _confidence = estimate
            if not isfinite(duration) or duration <= 0:
                return None
            # Remove worker speed from the duration when speed is available so
            # the weight reflects task work rather than machine throughput.
            value = duration * worker.speed
            if not isfinite(value) or value <= 0:
                return None
            values.append(value)
        return median(values) if values else None

    def choose(
        self,
        tasks: list[Task],
        workers: list[WorkerSlot],
        estimator: ScenarioEstimator,
        *,
        progress: Mapping[str, float | ProgressSnapshot] | None = None,
        now: float = 0.0,
        wait_objective: float | None = None,
    ) -> Decision:
        policy_version = self.version
        active = [worker for worker in workers if worker.enabled]
        if not tasks or not active:
            return self._fallback("empty_queue_or_pool", policy_version)
        if len({task.task_id for task in tasks}) != len(tasks):
            return self._fallback("duplicate_task_id", policy_version)
        if len({worker.worker_id for worker in active}) != len(active):
            return self._fallback("duplicate_worker_id", policy_version)
        if progress is None:
            return self._fallback("progress_snapshot_required", policy_version)
        task_ids = {task.task_id for task in tasks}
        if set(progress) != task_ids:
            return self._fallback("progress_snapshot_mismatch", policy_version)

        normalized: dict[str, float] = {}
        for task in tasks:
            if task.task_id not in progress:
                return self._fallback("progress_snapshot_incomplete", policy_version)
            value = progress[task.task_id]
            fraction = value.fraction if isinstance(value, ProgressSnapshot) else value
            if not isinstance(fraction, (int, float)) or not isfinite(fraction):
                return self._fallback("invalid_progress_snapshot", policy_version)
            if not 0.0 <= float(fraction) <= 1.0:
                return self._fallback("progress_out_of_bounds", policy_version)
            normalized[task.task_id] = max(float(fraction), self.lease_reservation)

        costs: dict[str, float] = {}
        for task in tasks:
            cost = self._cost(task, active, estimator)
            if cost is None:
                return self._fallback("invalid_or_missing_cost_estimate", policy_version)
            costs[task.task_id] = cost

        totals: dict[str, float] = {}
        progress_cost: dict[str, float] = {}
        for task in tasks:
            totals[task.scenario] = totals.get(task.scenario, 0.0) + costs[task.task_id]
            progress_cost[task.scenario] = progress_cost.get(task.scenario, 0.0) + (
                costs[task.task_id] * normalized[task.task_id]
            )
        scores = {
            scenario: progress_cost[scenario] / total
            for scenario, total in totals.items()
            if isfinite(total) and total > 0
        }
        if not scores:
            return self._fallback("no_valid_scenario_score", policy_version)
        minimum = min(scores.values())
        selected_scenarios = {
            scenario for scenario, score in scores.items() if score == minimum
        }
        candidates = [task for task in tasks if task.scenario in selected_scenarios]
        assert self.base_policy is not None
        decision = self.base_policy.choose(
            candidates, active, estimator, now=now, wait_objective=wait_objective
        )
        if decision.action != "dispatch":
            return self._fallback("selected_scenario_not_dispatchable", policy_version)
        return Decision(
            decision.action,
            decision.task_id,
            decision.worker_id,
            decision.projected_makespan,
            decision.confidence,
            f"cost_weighted_progress_fair_share:{minimum:.6f}",
            policy_version,
        )
