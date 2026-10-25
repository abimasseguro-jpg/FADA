"""Read-only bridge from estimator 0.2 to the existing policy estimate shape."""

from __future__ import annotations

from dataclasses import dataclass, field

from .domain import Task, WorkerSlot
from .estimation_v02 import EstimatorContext, StratifiedDurationEstimator


@dataclass(slots=True)
class PolicyEstimatorAdapter:
    """Expose `(seconds, confidence)` without changing policy 0.1/0.4 code."""

    estimator: StratifiedDurationEstimator
    backend: str
    hardware_profile: str
    now: float | None = None
    _cache: dict[tuple[str, str, float], tuple[float, float] | None] = field(
        default_factory=dict, init=False, repr=False
    )

    def __post_init__(self) -> None:
        if not self.backend or not self.hardware_profile:
            raise ValueError("adapter backend and hardware profile are required")

    def estimate(self, task: Task, worker: WorkerSlot) -> tuple[float, float] | None:
        key = (task.scenario, worker.machine, task.complexity)
        if self.now is not None and key in self._cache:
            return self._cache[key]
        value = self.estimator.estimate(
            EstimatorContext(task.scenario, worker.machine, self.backend, self.hardware_profile),
            complexity=task.complexity,
            now=self.now,
        )
        result = None if value is None else (value.point_seconds, value.confidence)
        if self.now is not None:
            self._cache[key] = result
        return result
