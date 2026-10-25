"""Plan-guarded FADA-HS 0.3 candidate.

Unlike 0.2, the guard compares complete estimated schedules.  A locally faster
assignment is not enough to leave Sufferage: after that assignment, the
remaining tasks must still yield a sufficiently smaller projected makespan.
"""

from __future__ import annotations

from dataclasses import dataclass

from .domain import Decision, Task, WorkerSlot
from .estimation import ScenarioEstimator
from .policy import HybridPolicy


@dataclass(slots=True)
class PlanGuardedHybridPolicy:
    """Hybrid proposal protected by a whole-plan Sufferage comparison."""

    version: str = "fada-hs/0.3"
    plan_safety_margin_fraction: float = 0.05
    candidate_window: int = 32
    projection_limit: int = 256
    uncertainty_weight: float = 1.0

    def __post_init__(self) -> None:
        if not self.version:
            raise ValueError("policy version must not be empty")
        if not 0.0 <= self.plan_safety_margin_fraction < 1.0:
            raise ValueError("plan safety margin must be in [0, 1)")

    @staticmethod
    def _eligible(task: Task, worker: WorkerSlot) -> bool:
        return worker.enabled and (
            not task.eligible_workers or worker.worker_id in task.eligible_workers
        )

    def _duration(
        self, task: Task, worker: WorkerSlot, estimator: ScenarioEstimator
    ) -> float | None:
        estimate = estimator.estimate(task, worker)
        if estimate is None:
            return None
        duration, confidence = estimate
        return duration * (1.0 + self.uncertainty_weight * (1.0 - confidence))

    def _sufferage(
        self,
        tasks: list[Task],
        workers: list[WorkerSlot],
        estimator: ScenarioEstimator,
        *,
        now: float,
    ) -> tuple[Task, WorkerSlot] | None:
        options: list[tuple[float, float, str, str, Task, WorkerSlot]] = []
        for task in tasks:
            ranked: list[tuple[float, str, WorkerSlot]] = []
            for worker in workers:
                if not self._eligible(task, worker):
                    continue
                duration = self._duration(task, worker, estimator)
                if duration is None:
                    continue
                ranked.append((max(now, worker.available_at) + duration, worker.worker_id, worker))
            if not ranked:
                return None
            ranked.sort()
            completion, _, worker = ranked[0]
            gap = ranked[1][0] - completion if len(ranked) > 1 else float("inf")
            options.append((-gap, completion, task.task_id, worker.worker_id, task, worker))
        return min(options)[4:]

    def _project_sufferage(
        self,
        tasks: list[Task],
        workers: list[WorkerSlot],
        estimator: ScenarioEstimator,
        *,
        now: float,
        first: tuple[Task, WorkerSlot] | None = None,
    ) -> float | None:
        remaining = list(tasks)
        projected = [
            WorkerSlot(w.worker_id, w.machine, w.speed, max(now, w.available_at), w.enabled)
            for w in workers if w.enabled
        ]
        if not projected:
            return None
        if first is not None:
            task, selected = first
            slot = next((item for item in projected if item.worker_id == selected.worker_id), None)
            if slot is None or task not in remaining or not self._eligible(task, slot):
                return None
            duration = self._duration(task, slot, estimator)
            if duration is None:
                return None
            projected[projected.index(slot)] = WorkerSlot(
                slot.worker_id, slot.machine, slot.speed, slot.available_at + duration, slot.enabled
            )
            remaining.remove(task)
        while remaining:
            selected = self._sufferage(remaining, projected, estimator, now=now)
            if selected is None:
                return None
            task, slot = selected
            duration = self._duration(task, slot, estimator)
            if duration is None:
                return None
            projected[projected.index(slot)] = WorkerSlot(
                slot.worker_id, slot.machine, slot.speed, slot.available_at + duration, slot.enabled
            )
            remaining.remove(task)
        return max(slot.available_at for slot in projected)

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
        baseline_pair = self._sufferage(tasks, active, estimator, now=now)
        baseline_plan = self._project_sufferage(tasks, active, estimator, now=now)
        if baseline_pair is None or baseline_plan is None:
            return Decision("fallback", None, None, None, 0.0, "baseline_insufficient_estimates", self.version)
        baseline_task, baseline_worker = baseline_pair
        baseline = Decision(
            "dispatch", baseline_task.task_id, baseline_worker.worker_id, baseline_plan, 1.0,
            "sufferage_whole_plan_guard", self.version,
        )
        candidate = HybridPolicy(
            version="fada-hs/0.1", candidate_window=self.candidate_window,
            projection_limit=self.projection_limit, uncertainty_weight=self.uncertainty_weight,
        ).choose(tasks, active, estimator, now=now, wait_objective=wait_objective)
        if candidate.action != "dispatch" or candidate.task_id is None or candidate.worker_id is None:
            return baseline
        task = next((item for item in tasks if item.task_id == candidate.task_id), None)
        worker = next((item for item in active if item.worker_id == candidate.worker_id), None)
        if task is None or worker is None:
            return baseline
        candidate_plan = self._project_sufferage(tasks, active, estimator, now=now, first=(task, worker))
        if candidate_plan is None:
            return baseline
        if candidate_plan < baseline_plan * (1.0 - self.plan_safety_margin_fraction):
            return Decision(
                "dispatch", task.task_id, worker.worker_id, candidate_plan, 1.0,
                "fada_candidate_beats_sufferage_whole_plan", self.version,
            )
        return baseline
