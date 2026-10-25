"""Guarded FADA-HS 0.2 candidate.

The candidate is deliberately side-effect free.  It compares the 0.1 proposal
with a Sufferage proposal for the same visible state and keeps Sufferage unless
the projected improvement is larger than a declared safety margin.  This makes
the baseline a real guard, rather than a post-hoc reporting comparator.
"""

from __future__ import annotations

from dataclasses import dataclass

from .domain import Decision, Task, WorkerSlot
from .estimation import ScenarioEstimator
from .policy import HybridPolicy


@dataclass(slots=True)
class GuardedHybridPolicy:
    """FADA-HS 0.2 with an explicit, deterministic Sufferage guard."""

    version: str = "fada-hs/0.2"
    safety_margin_fraction: float = 0.10
    candidate_window: int = 32
    projection_limit: int = 256
    uncertainty_weight: float = 1.0

    def __post_init__(self) -> None:
        if not self.version:
            raise ValueError("policy version must not be empty")
        if not 0.0 <= self.safety_margin_fraction < 1.0:
            raise ValueError("safety margin must be in [0, 1)")

    @staticmethod
    def _eligible(task: Task, worker: WorkerSlot) -> bool:
        return worker.enabled and (
            not task.eligible_workers or worker.worker_id in task.eligible_workers
        )

    def _baseline(
        self, tasks: list[Task], workers: list[WorkerSlot], estimator: ScenarioEstimator, now: float
    ) -> tuple[Decision, float] | None:
        active = [worker for worker in workers if worker.enabled]
        options: list[tuple[float, float, str, str, float]] = []
        for task in tasks:
            ranked: list[tuple[float, str, WorkerSlot]] = []
            for worker in active:
                if not self._eligible(task, worker):
                    continue
                estimate = estimator.estimate(task, worker)
                if estimate is None:
                    continue
                ranked.append((max(now, worker.available_at) + estimate[0], worker.worker_id, worker))
            if not ranked:
                return None
            ranked.sort()
            best_completion, _, best_worker = ranked[0]
            gap = ranked[1][0] - best_completion if len(ranked) > 1 else float("inf")
            # The stable IDs make equal proposals reproducible.
            options.append((-gap, best_completion, task.task_id, best_worker.worker_id, best_completion))
        _, _, task_id, worker_id, completion = min(options)
        return (
            Decision(
                "dispatch", task_id, worker_id, completion, 1.0,
                "sufferage_baseline_guard", policy_version=self.version,
            ),
            completion,
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
        candidate = HybridPolicy(
            version="fada-hs/0.1",
            candidate_window=self.candidate_window,
            projection_limit=self.projection_limit,
            uncertainty_weight=self.uncertainty_weight,
        ).choose(tasks, workers, estimator, now=now, wait_objective=wait_objective)
        baseline = self._baseline(tasks, workers, estimator, now)
        if baseline is None:
            return Decision("fallback", None, None, None, 0.0, "baseline_insufficient_estimates", self.version)
        baseline_decision, baseline_completion = baseline
        if candidate.action != "dispatch" or candidate.task_id is None or candidate.worker_id is None:
            return baseline_decision
        candidate_worker = next((worker for worker in workers if worker.worker_id == candidate.worker_id), None)
        candidate_task = next((task for task in tasks if task.task_id == candidate.task_id), None)
        if candidate_worker is None or candidate_task is None or not self._eligible(candidate_task, candidate_worker):
            return baseline_decision
        estimate = estimator.estimate(candidate_task, candidate_worker)
        if estimate is None:
            return baseline_decision
        duration, confidence = estimate
        candidate_completion = max(now, candidate_worker.available_at) + duration
        required = baseline_completion * (1.0 - self.safety_margin_fraction * confidence)
        if candidate_completion < required:
            return Decision(
                "dispatch", candidate.task_id, candidate.worker_id,
                candidate.projected_makespan, confidence,
                "fada_candidate_beats_sufferage_guard", self.version,
            )
        return baseline_decision
