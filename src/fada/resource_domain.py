"""Validated, queue-independent contracts for FADA Resource Controller 0.1."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Protocol


RESOURCE_TELEMETRY_SCHEMA_VERSION = "fada-resource-telemetry/v1"
CAPACITY_RECOMMENDATION_SCHEMA_VERSION = "fada-capacity-recommendation/v1"


class ResourceMode(str, Enum):
    DISABLED = "disabled"
    SHADOW = "shadow"
    ADVISORY = "advisory"
    ACTIVE = "active"


class CapacityAction(str, Enum):
    KEEP = "keep"
    INCREASE_WORKERS = "increase_workers"
    DECREASE_WORKERS = "decrease_workers"
    INCREASE_CLOCK = "increase_clock"
    DECREASE_CLOCK = "decrease_clock"
    CHANGE_WORKERS_AND_CLOCK = "change_workers_and_clock"
    EMERGENCY_DECREASE = "emergency_decrease"
    FALLBACK = "fallback"


@dataclass(frozen=True, slots=True)
class CapacityLevel:
    """One capacity setting explicitly authorized by the host project."""

    level_id: str
    workers: int
    core_clock_hz: int

    def __post_init__(self) -> None:
        if not isinstance(self.level_id, str) or not self.level_id:
            raise ValueError("capacity level id must not be empty")
        if isinstance(self.workers, bool) or not isinstance(self.workers, int) or self.workers <= 0:
            raise ValueError("capacity workers must be positive")
        if (
            isinstance(self.core_clock_hz, bool)
            or not isinstance(self.core_clock_hz, int)
            or self.core_clock_hz <= 0
        ):
            raise ValueError("capacity core clock must be positive")

    @property
    def load_proxy(self) -> int:
        """Ordering proxy only; never used as a performance or power estimate."""

        return self.workers * self.core_clock_hz


@dataclass(frozen=True, slots=True)
class MachineResourceConfig:
    machine_id: str
    authorized_levels: tuple[CapacityLevel, ...]
    mode: ResourceMode = ResourceMode.DISABLED
    minimum_samples_per_level: int = 3
    observation_window_seconds: float = 900.0
    telemetry_max_age_seconds: float = 60.0
    cooldown_seconds: float = 300.0
    minimum_throughput_gain_ratio: float = 0.03
    memory_reserve_bytes: int = 0
    maximum_swap_used_bytes: int = 0
    maximum_error_rate: float = 0.0
    thermal_warning_celsius: float = 80.0
    thermal_critical_celsius: float = 90.0
    thermal_hysteresis_celsius: float = 3.0
    maximum_temperature_rise_celsius_per_second: float | None = None
    throughput_uncertainty_multiplier: float = 2.0

    def __post_init__(self) -> None:
        if not isinstance(self.machine_id, str) or not self.machine_id:
            raise ValueError("machine id must not be empty")
        if not self.authorized_levels:
            raise ValueError("at least one authorized capacity level is required")
        if not isinstance(self.mode, ResourceMode):
            raise TypeError("resource mode must be a ResourceMode")
        ids = [level.level_id for level in self.authorized_levels]
        settings = [
            (level.workers, level.core_clock_hz) for level in self.authorized_levels
        ]
        if len(ids) != len(set(ids)):
            raise ValueError("capacity level ids must be unique")
        if len(settings) != len(set(settings)):
            raise ValueError("capacity worker/clock settings must be unique")
        if self.minimum_samples_per_level <= 0:
            raise ValueError("minimum samples per level must be positive")
        for name, value in (
            ("observation window", self.observation_window_seconds),
            ("telemetry max age", self.telemetry_max_age_seconds),
            ("cooldown", self.cooldown_seconds),
        ):
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if (
            not isfinite(self.minimum_throughput_gain_ratio)
            or self.minimum_throughput_gain_ratio < 0
        ):
            raise ValueError("minimum throughput gain ratio must be finite and non-negative")
        if self.memory_reserve_bytes < 0 or self.maximum_swap_used_bytes < 0:
            raise ValueError("memory and swap bounds cannot be negative")
        if not 0 <= self.maximum_error_rate <= 1:
            raise ValueError("maximum error rate must be between zero and one")
        if not (
            isfinite(self.thermal_warning_celsius)
            and isfinite(self.thermal_critical_celsius)
            and self.thermal_warning_celsius >= 0
            and self.thermal_warning_celsius < self.thermal_critical_celsius
        ):
            raise ValueError("thermal warning must be below a finite critical limit")
        if (
            not isfinite(self.thermal_hysteresis_celsius)
            or self.thermal_hysteresis_celsius < 0
        ):
            raise ValueError("thermal hysteresis must be finite and non-negative")
        if self.maximum_temperature_rise_celsius_per_second is not None and (
            not isfinite(self.maximum_temperature_rise_celsius_per_second)
            or self.maximum_temperature_rise_celsius_per_second <= 0
        ):
            raise ValueError("maximum temperature rise must be finite and positive")
        if (
            not isfinite(self.throughput_uncertainty_multiplier)
            or self.throughput_uncertainty_multiplier < 0
        ):
            raise ValueError("throughput uncertainty multiplier must be non-negative")

    def level(self, level_id: str) -> CapacityLevel:
        for level in self.authorized_levels:
            if level.level_id == level_id:
                return level
        raise ValueError(f"capacity level is not authorized: {level_id}")


@dataclass(frozen=True, slots=True)
class ResourceTelemetry:
    observation_id: str
    machine_id: str
    observed_at: float
    level_id: str
    active_workers: int
    effective_core_clock_hz: int
    throughput_tasks_per_second: float
    temperature_celsius: float
    memory_available_bytes: int
    swap_used_bytes: int
    error_rate: float = 0.0
    stable: bool = True
    thermal_throttled: bool = False
    schema_version: str = RESOURCE_TELEMETRY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, str) and value
            for value in (self.observation_id, self.machine_id, self.level_id)
        ):
            raise ValueError("telemetry identities must not be empty")
        if self.schema_version != RESOURCE_TELEMETRY_SCHEMA_VERSION:
            raise ValueError("unsupported telemetry schema version")
        if not isinstance(self.stable, bool) or not isinstance(
            self.thermal_throttled, bool
        ):
            raise TypeError("telemetry state flags must be boolean")
        if not isfinite(self.observed_at) or self.observed_at < 0:
            raise ValueError("observation time must be finite and non-negative")
        if (
            isinstance(self.active_workers, bool)
            or not isinstance(self.active_workers, int)
            or isinstance(self.effective_core_clock_hz, bool)
            or not isinstance(self.effective_core_clock_hz, int)
            or self.active_workers <= 0
            or self.effective_core_clock_hz <= 0
        ):
            raise ValueError("observed workers and clock must be positive")
        if (
            not isfinite(self.throughput_tasks_per_second)
            or self.throughput_tasks_per_second < 0
        ):
            raise ValueError("throughput must be finite and non-negative")
        if not isfinite(self.temperature_celsius):
            raise ValueError("temperature must be finite")
        if self.memory_available_bytes < 0 or self.swap_used_bytes < 0:
            raise ValueError("memory and swap observations cannot be negative")
        if not isfinite(self.error_rate) or not 0 <= self.error_rate <= 1:
            raise ValueError("error rate must be finite and between zero and one")


@dataclass(frozen=True, slots=True)
class CapacityRecommendation:
    machine_id: str
    mode: ResourceMode
    action: CapacityAction
    current_level_id: str
    recommended_level_id: str
    apply_allowed: bool
    reason: str
    confidence: float
    observation_id: str | None
    idempotency_key: str
    controller_version: str = "fada-rc/0.1"
    predicted_throughput_tasks_per_second: float | None = None
    throughput_lower_bound: float | None = None
    throughput_upper_bound: float | None = None
    temperature_rise_celsius_per_second: float | None = None
    schema_version: str = CAPACITY_RECOMMENDATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not all(
            (
                self.machine_id,
                self.current_level_id,
                self.recommended_level_id,
                self.reason,
                self.idempotency_key,
                self.controller_version,
            )
        ):
            raise ValueError("recommendation identities and reason must not be empty")
        if self.schema_version != CAPACITY_RECOMMENDATION_SCHEMA_VERSION:
            raise ValueError("unsupported recommendation schema version")
        if not isinstance(self.mode, ResourceMode) or not isinstance(
            self.action, CapacityAction
        ):
            raise TypeError("recommendation mode and action must use their enums")
        if not isinstance(self.apply_allowed, bool):
            raise TypeError("apply_allowed must be boolean")
        if not isfinite(self.confidence) or not 0 <= self.confidence <= 1:
            raise ValueError("recommendation confidence must be between zero and one")
        for name, value in (
            ("predicted throughput", self.predicted_throughput_tasks_per_second),
            ("throughput lower bound", self.throughput_lower_bound),
            ("throughput upper bound", self.throughput_upper_bound),
        ):
            if value is not None and (not isfinite(value) or value < 0):
                raise ValueError(f"{name} must be finite and non-negative")
        if (
            self.throughput_lower_bound is not None
            and self.throughput_upper_bound is not None
            and self.throughput_lower_bound > self.throughput_upper_bound
        ):
            raise ValueError("throughput bounds are inverted")
        if self.temperature_rise_celsius_per_second is not None and not isfinite(
            self.temperature_rise_celsius_per_second
        ):
            raise ValueError("temperature rise must be finite")
        if self.apply_allowed and (
            self.mode is not ResourceMode.ACTIVE
            or self.action in {CapacityAction.KEEP, CapacityAction.FALLBACK}
        ):
            raise ValueError("only an active capacity change may be applied")


@dataclass(frozen=True, slots=True)
class CapacityReceipt:
    idempotency_key: str
    accepted: bool
    observed_level_id: str | None
    reason: str

    def __post_init__(self) -> None:
        if not self.idempotency_key or not self.reason:
            raise ValueError("receipt idempotency key and reason must not be empty")


class CapacityActuator(Protocol):
    """Host-owned boundary. The Resource Controller never invokes it itself."""

    def request_capacity(
        self, recommendation: CapacityRecommendation
    ) -> CapacityReceipt: ...


class NoOpCapacityActuator:
    """Safe integration default that cannot modify workers or CPU frequency."""

    def request_capacity(
        self, recommendation: CapacityRecommendation
    ) -> CapacityReceipt:
        return CapacityReceipt(
            idempotency_key=recommendation.idempotency_key,
            accepted=False,
            observed_level_id=recommendation.current_level_id,
            reason="no_op_actuator",
        )
