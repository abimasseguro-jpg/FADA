"""Bounded FADA-HS reference policy.

HS denotes the hybrid use of makespan projection and Sufferage as a tie-breaker.
The implementation is intentionally side-effect free: queue adapters own dispatch.
"""

from __future__ import annotations

from dataclasses import dataclass

from .domain import Decision, Task, WorkerSlot
from .estimation import ScenarioEstimator


@dataclass(slots=True)
class HybridPolicy:
    version: str = "fada-hs/0.1"
    candidate_window: int = 32
    projection_limit: int = 256
    uncertainty_weight: float = 1.0
    epsilon_seconds: float = 0.0

    def __post_init__(self) -> None:
        if not self.version:
            raise ValueError("policy version must not be empty")
        if self.candidate_window <= 0:
            raise ValueError("candidate window must be positive")
        if self.projection_limit < 0:
            raise ValueError("projection limit cannot be negative")
        if self.uncertainty_weight < 0:
            raise ValueError("uncertainty weight cannot be negative")
        if self.epsilon_seconds < 0:
            raise ValueError("epsilon cannot be negative")

    @staticmethod
    def _eligible(task: Task, worker: WorkerSlot) -> bool:
        return worker.enabled and (
            not task.eligible_workers or worker.worker_id in task.eligible_workers
        )

    def choose(
        self,
        tasks: list[Task],
        workers: list[WorkerSlot],
        estimator: ScenarioEstimator,
        *,
        now: float = 0.0,
        wait_objective: float | None = None,
    ) -> Decision:
        active = [worker for worker in workers if worker.enabled]
        if not tasks or not active:
            return self._decision(
                "fallback", None, None, None, 0.0, "empty_queue_or_pool"
            )
        if len({task.task_id for task in tasks}) != len(tasks):
            return self._decision(
                "fallback", None, None, None, 0.0, "duplicate_task_id"
            )
        if len({worker.worker_id for worker in active}) != len(active):
            return self._decision(
                "fallback", None, None, None, 0.0, "duplicate_worker_id"
            )

        estimates: dict[tuple[str, str], tuple[float, float]] = {}
        for task in tasks:
            for worker in active:
                if self._eligible(task, worker):
                    value = estimator.estimate(task, worker)
                    if value is not None:
                        estimates[(task.task_id, worker.worker_id)] = value
        if not estimates:
            return self._decision(
                "fallback", None, None, None, 0.0, "insufficient_estimates"
            )
        if any(
            not any((task.task_id, worker.worker_id) in estimates for worker in active)
            for task in tasks
        ):
            return self._decision(
                "fallback", None, None, None, 0.0,
                "partial_estimate_coverage",
            )

        def robust_estimate(task: Task, worker: WorkerSlot) -> float:
            duration, confidence = estimates[(task.task_id, worker.worker_id)]
            return duration * (1.0 + self.uncertainty_weight * (1.0 - confidence))

        def best_duration(task: Task) -> float:
            values = [
                duration
                for worker in active
                if (value := estimates.get((task.task_id, worker.worker_id)))
                for duration in [value[0]]
            ]
            return min(values) if values else float("inf")

        candidates = sorted(
            tasks,
            key=lambda task: (-task.priority, -best_duration(task), task.task_id),
        )[: self.candidate_window]
        options: list[tuple[float, float, float, str, str]] = []
        for task in candidates:
            completion_times = sorted(
                max(now, worker.available_at) + estimates[(task.task_id, worker.worker_id)][0]
                for worker in active
                if (task.task_id, worker.worker_id) in estimates
            )
            sufferage = (
                completion_times[1] - completion_times[0]
                if len(completion_times) > 1
                else float("inf")
            )
            for worker in active:
                estimate = estimates.get((task.task_id, worker.worker_id))
                if estimate is None:
                    continue
                _, confidence = estimate
                loads = {slot.worker_id: max(now, slot.available_at) for slot in active}
                loads[worker.worker_id] += robust_estimate(task, worker)
                remaining = [item for item in tasks if item.task_id != task.task_id]
                remaining.sort(key=best_duration, reverse=True)
                for item in remaining[: self.projection_limit]:
                    feasible = [
                        slot
                        for slot in active
                        if (item.task_id, slot.worker_id) in estimates
                    ]
                    if not feasible:
                        continue
                    selected = min(
                        feasible,
                        key=lambda slot: loads[slot.worker_id]
                        + robust_estimate(item, slot),
                    )
                    loads[selected.worker_id] += robust_estimate(item, selected)
                makespan = max(loads.values())
                # Sufferage is a deterministic tie-breaker, not a different unit
                # mixed into makespan.
                options.append(
                    (makespan, -sufferage, -confidence, task.task_id, worker.worker_id)
                )

        if not options:
            return self._decision(
                "fallback", None, None, None, 0.0, "no_eligible_assignment"
            )
        objective, _, neg_confidence, task_id, worker_id = min(options)
        confidence = -neg_confidence
        if (
            wait_objective is not None
            and objective - wait_objective > self.epsilon_seconds
        ):
            return self._decision(
                "wait", None, None, objective, confidence,
                "wait_improves_objective_beyond_safety_margin",
            )
        return self._decision(
            "dispatch", task_id, worker_id, objective, confidence,
            "minimum_robust_projected_makespan",
        )

    def _decision(
        self,
        action: str,
        task_id: str | None,
        worker_id: str | None,
        projected_makespan: float | None,
        confidence: float,
        reason: str,
    ) -> Decision:
        return Decision(
            action,
            task_id,
            worker_id,
            projected_makespan,
            confidence,
            reason,
            policy_version=self.version,
        )
