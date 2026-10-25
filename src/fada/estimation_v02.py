"""Stratified duration estimation, separate from the frozen 0.1 baseline."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite

from .observations import DurationObservation


DURATION_ESTIMATE_SCHEMA_VERSION = "fada-duration-estimate/v1"
ESTIMATOR_V02_VERSION = "fada-estimator/0.2"


@dataclass(frozen=True, slots=True)
class EstimatorContext:
    scenario: str
    machine_id: str
    backend: str
    hardware_profile: str

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) and value for value in (
            self.scenario, self.machine_id, self.backend, self.hardware_profile
        )):
            raise ValueError("estimator context identities must not be empty")


@dataclass(frozen=True, slots=True)
class DurationEstimate:
    point_seconds: float
    p50_seconds: float
    p95_seconds: float
    lower_seconds: float
    upper_seconds: float
    confidence: float
    sample_count: int
    source: str
    drift_detected: bool = False
    regime_started_at: float | None = None
    estimator_version: str = ESTIMATOR_V02_VERSION
    schema_version: str = DURATION_ESTIMATE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != DURATION_ESTIMATE_SCHEMA_VERSION:
            raise ValueError("unsupported duration estimate schema")
        if self.estimator_version != ESTIMATOR_V02_VERSION:
            raise ValueError("unsupported estimator version")
        if not self.source or self.sample_count < 0:
            raise ValueError("duration estimate provenance is invalid")
        if not isinstance(self.drift_detected, bool):
            raise TypeError("drift state must be boolean")
        if self.regime_started_at is not None and (
            not isfinite(self.regime_started_at) or self.regime_started_at < 0
        ):
            raise ValueError("regime start must be finite and non-negative")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("duration estimate confidence must be in [0, 1]")
        values = (self.lower_seconds, self.p50_seconds, self.point_seconds,
                  self.p95_seconds, self.upper_seconds)
        if not all(isfinite(value) and value > 0 for value in values):
            raise ValueError("duration estimate values must be finite and positive")
        if not self.lower_seconds <= self.p50_seconds <= self.p95_seconds <= self.upper_seconds:
            raise ValueError("duration estimate quantiles and interval must be ordered")


def _weighted_quantile(values: list[tuple[float, float]], probability: float) -> float:
    if not values:
        raise ValueError("quantile requires values")
    ordered = sorted(values)
    total = sum(weight for _, weight in ordered)
    if not isfinite(total) or total <= 0:
        raise ValueError("quantile weights must be finite and positive")
    target = probability * total
    cumulative = 0.0
    for index, (value, weight) in enumerate(ordered):
        cumulative += weight
        if cumulative == target and index + 1 < len(ordered):
            return (value + ordered[index + 1][0]) / 2.0
        if cumulative >= target:
            return value
    return ordered[-1][0]


@dataclass(slots=True)
class StratifiedDurationEstimator:
    """Estimate only within compatible scenario/backend/hardware strata.

    It accepts every outcome as evidence, but only completed observations are
    eligible as duration samples.  Its sole fallback changes machine identity;
    backend and hardware profile always remain identical.
    """

    minimum_samples: int = 3
    cold_start_seconds: float | None = None
    recency_half_life_seconds: float = 3600.0
    drift_window_seconds: float = 3600.0
    drift_minimum_samples: int = 3
    drift_ratio_threshold: float = 1.25
    _observations: list[DurationObservation] = field(default_factory=list)
    _ids: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.minimum_samples <= 0:
            raise ValueError("minimum samples must be positive")
        if self.cold_start_seconds is not None and (
            not isfinite(self.cold_start_seconds) or self.cold_start_seconds <= 0
        ):
            raise ValueError("cold start must be finite and positive")
        for name, value in (
            ("recency half life", self.recency_half_life_seconds),
            ("drift window", self.drift_window_seconds),
        ):
            if not isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if self.drift_minimum_samples <= 0:
            raise ValueError("drift minimum samples must be positive")
        if not isfinite(self.drift_ratio_threshold) or self.drift_ratio_threshold <= 1:
            raise ValueError("drift ratio threshold must be greater than one")

    def observe(self, observation: DurationObservation) -> None:
        if observation.observation_id in self._ids:
            raise ValueError("duplicate duration observation identity")
        self._ids.add(observation.observation_id)
        self._observations.append(observation)

    def _completed(
        self, context: EstimatorContext, *, exact_machine: bool, now: float
    ) -> list[DurationObservation]:
        values: list[DurationObservation] = []
        for observation in self._observations:
            if (
                observation.scenario != context.scenario
                or observation.backend != context.backend
                or observation.hardware_profile != context.hardware_profile
                or (exact_machine and observation.machine_id != context.machine_id)
            ):
                continue
            if observation.observed_at <= now and observation.completed_duration_seconds is not None:
                values.append(observation)
        return values

    def _regime(
        self, observations: list[DurationObservation], now: float
    ) -> tuple[list[DurationObservation], bool, float | None]:
        """Return the recent regime only when a two-window shift is material."""

        window = sorted(
            (item for item in observations if now - item.observed_at <= self.drift_window_seconds),
            key=lambda item: (item.observed_at, item.observation_id),
        )
        if len(window) < 2 * self.drift_minimum_samples:
            return observations, False, None
        split = len(window) // 2
        before, after = window[:split], window[split:]
        before_values = [item.completed_duration_seconds for item in before]
        after_values = [item.completed_duration_seconds for item in after]
        # `completed_duration_seconds` is non-null by construction in _completed.
        before_median = _weighted_quantile([(float(item), 1.0) for item in before_values if item is not None], 0.5)
        after_median = _weighted_quantile([(float(item), 1.0) for item in after_values if item is not None], 0.5)
        ratio = max(before_median, after_median) / min(before_median, after_median)
        if ratio >= self.drift_ratio_threshold:
            return after, True, after[0].observed_at
        return observations, False, None

    def _weighted_values(
        self, observations: list[DurationObservation], now: float, complexity: float
    ) -> list[tuple[float, float]]:
        return [
            (
                float(observation.completed_duration_seconds),
                0.5 ** ((now - observation.observed_at) / self.recency_half_life_seconds),
            )
            for observation in observations
            if observation.completed_duration_seconds is not None
        ]

    def estimate(
        self, context: EstimatorContext, *, complexity: float = 1.0, now: float | None = None
    ) -> DurationEstimate | None:
        if not isfinite(complexity) or complexity <= 0:
            raise ValueError("complexity must be finite and positive")
        latest = max((item.observed_at for item in self._observations), default=0.0)
        evaluation_time = latest if now is None else now
        if not isfinite(evaluation_time) or evaluation_time < 0:
            raise ValueError("estimation time must be finite and non-negative")
        exact = self._completed(context, exact_machine=True, now=evaluation_time)
        values, source = (exact, "exact") if exact else (
            self._completed(context, exact_machine=False, now=evaluation_time), "compatible_hardware_fallback"
        )
        if not values:
            if self.cold_start_seconds is None:
                return None
            weighted = [(self.cold_start_seconds, 1.0)]
            sample_count, drift_detected, regime_started_at = 1, False, None
            source = "explicit_cold_start"
        else:
            regime, drift_detected, regime_started_at = self._regime(values, evaluation_time)
            weighted = self._weighted_values(regime, evaluation_time, complexity)
            sample_count = len(regime)
            if drift_detected:
                source += "_recent_regime"

        p50, p95 = _weighted_quantile(weighted, 0.50), _weighted_quantile(weighted, 0.95)
        lower, upper = _weighted_quantile(weighted, 0.05), p95
        p50, p95, lower, upper = (value * complexity for value in (p50, p95, lower, upper))
        confidence = min(1.0, sample_count / self.minimum_samples)
        if not source.startswith("exact"):
            confidence = min(confidence, 0.5 if source.startswith("compatible_hardware_fallback") else 0.15)
        return DurationEstimate(
            point_seconds=p50, p50_seconds=p50, p95_seconds=p95,
            lower_seconds=lower, upper_seconds=upper, confidence=confidence,
            sample_count=sample_count, source=source, drift_detected=drift_detected,
            regime_started_at=regime_started_at,
        )
