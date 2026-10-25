"""Domain objects independent of any queue implementation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Task:
    task_id: str
    scenario: str
    complexity: float = 1.0
    priority: int = 0
    eligible_workers: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if self.complexity <= 0:
            raise ValueError("task complexity must be positive")


@dataclass(frozen=True, slots=True)
class WorkerSlot:
    worker_id: str
    machine: str
    speed: float = 1.0
    available_at: float = 0.0
    enabled: bool = True

    def __post_init__(self) -> None:
        if self.speed <= 0:
            raise ValueError("worker speed must be positive")
        if self.available_at < 0:
            raise ValueError("worker availability cannot be negative")


@dataclass(frozen=True, slots=True)
class Decision:
    action: str
    task_id: str | None
    worker_id: str | None
    projected_makespan: float | None
    confidence: float
    reason: str
    policy_version: str = "fada-hs/0.1"

