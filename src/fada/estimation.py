"""Robust scenario/worker execution-time estimator."""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Iterable

from .domain import Task, WorkerSlot


@dataclass(slots=True)
class ScenarioEstimator:
    """Estimate p(i,s)=C(k_i)*m_i/v_s with robust online observations."""

    cold_start_seconds: float | None = None
    minimum_samples: int = 3
    _samples: dict[tuple[str, str], list[float]] = field(default_factory=dict)

    def observe(self, scenario: str, machine: str, elapsed_seconds: float) -> None:
        if elapsed_seconds <= 0:
            raise ValueError("elapsed time must be positive")
        self._samples.setdefault((scenario, machine), []).append(elapsed_seconds)

    def extend(
        self, observations: Iterable[tuple[str, str, float]]
    ) -> None:
        for scenario, machine, elapsed in observations:
            self.observe(scenario, machine, elapsed)

    def estimate(self, task: Task, worker: WorkerSlot) -> tuple[float, float] | None:
        direct = self._samples.get((task.scenario, worker.machine), [])
        if direct:
            base = median(direct)
            confidence = min(1.0, len(direct) / max(1, self.minimum_samples))
            return base * task.complexity, confidence

        scenario_samples = [
            value
            for (scenario, _), values in self._samples.items()
            if scenario == task.scenario
            for value in values
        ]
        if scenario_samples:
            return median(scenario_samples) * task.complexity / worker.speed, 0.4
        if self.cold_start_seconds is not None:
            return self.cold_start_seconds * task.complexity / worker.speed, 0.15
        return None

