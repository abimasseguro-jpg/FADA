"""Observed-only concurrency curves for duration and capacity consumers."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from statistics import median


CONCURRENCY_SAMPLE_SCHEMA_VERSION = "fada-concurrency-sample/v1"
CONCURRENCY_ESTIMATE_SCHEMA_VERSION = "fada-concurrency-estimate/v1"


@dataclass(frozen=True, slots=True)
class ConcurrencySample:
    observation_id: str
    machine_id: str
    backend: str
    hardware_profile: str
    active_workers: int
    completed_tasks: int
    elapsed_seconds: float
    observed_at: float
    stable: bool = True
    schema_version: str = CONCURRENCY_SAMPLE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != CONCURRENCY_SAMPLE_SCHEMA_VERSION:
            raise ValueError("unsupported concurrency sample schema")
        if not all(isinstance(value, str) and value for value in (
            self.observation_id, self.machine_id, self.backend, self.hardware_profile,
        )):
            raise ValueError("concurrency identities must not be empty")
        for name, value in (("active workers", self.active_workers), ("completed tasks", self.completed_tasks)):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if not isfinite(self.elapsed_seconds) or self.elapsed_seconds <= 0:
            raise ValueError("elapsed seconds must be finite and positive")
        if not isfinite(self.observed_at) or self.observed_at < 0:
            raise ValueError("observation time must be finite and non-negative")
        if not isinstance(self.stable, bool):
            raise TypeError("stability must be boolean")

    @property
    def throughput_tasks_per_second(self) -> float:
        return self.completed_tasks / self.elapsed_seconds


@dataclass(frozen=True, slots=True)
class ThroughputEstimate:
    machine_id: str
    backend: str
    hardware_profile: str
    active_workers: int
    throughput_tasks_per_second: float
    sample_count: int
    observed: bool
    schema_version: str = CONCURRENCY_ESTIMATE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != CONCURRENCY_ESTIMATE_SCHEMA_VERSION:
            raise ValueError("unsupported concurrency estimate schema")
        if self.active_workers <= 0 or self.sample_count <= 0:
            raise ValueError("concurrency estimate counts must be positive")
        if not isfinite(self.throughput_tasks_per_second) or self.throughput_tasks_per_second < 0:
            raise ValueError("throughput must be finite and non-negative")
        if not isinstance(self.observed, bool) or not self.observed:
            raise ValueError("unobserved concurrency extrapolation is not an estimate")


@dataclass(slots=True)
class ObservedConcurrencyCurve:
    """A context-isolated curve; no unobserved worker level is inferred."""

    minimum_samples_per_level: int = 3
    _samples: list[ConcurrencySample] = field(default_factory=list)
    _ids: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.minimum_samples_per_level <= 0:
            raise ValueError("minimum samples per level must be positive")

    def observe(self, sample: ConcurrencySample) -> None:
        if sample.observation_id in self._ids:
            raise ValueError("duplicate concurrency observation identity")
        self._ids.add(sample.observation_id)
        self._samples.append(sample)

    def estimate(
        self, *, machine_id: str, backend: str, hardware_profile: str, active_workers: int
    ) -> ThroughputEstimate | None:
        if not all(isinstance(value, str) and value for value in (machine_id, backend, hardware_profile)):
            raise ValueError("concurrency context identities must not be empty")
        if isinstance(active_workers, bool) or not isinstance(active_workers, int) or active_workers <= 0:
            raise ValueError("active workers must be a positive integer")
        samples = [
            item for item in self._samples
            if item.machine_id == machine_id and item.backend == backend
            and item.hardware_profile == hardware_profile and item.active_workers == active_workers
            and item.stable
        ]
        if len(samples) < self.minimum_samples_per_level:
            return None
        return ThroughputEstimate(
            machine_id=machine_id, backend=backend, hardware_profile=hardware_profile,
            active_workers=active_workers,
            throughput_tasks_per_second=median(item.throughput_tasks_per_second for item in samples),
            sample_count=len(samples), observed=True,
        )

    def best_observed_workers(
        self, *, machine_id: str, backend: str, hardware_profile: str
    ) -> int | None:
        levels = sorted({
            item.active_workers for item in self._samples
            if item.machine_id == machine_id and item.backend == backend
            and item.hardware_profile == hardware_profile
        })
        estimates = [
            estimate for workers in levels
            if (estimate := self.estimate(
                machine_id=machine_id, backend=backend, hardware_profile=hardware_profile,
                active_workers=workers,
            )) is not None
        ]
        if not estimates:
            return None
        return min(
            estimates,
            key=lambda item: (-item.throughput_tasks_per_second, item.active_workers),
        ).active_workers
