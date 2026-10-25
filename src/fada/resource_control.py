"""Side-effect-free adaptive capacity recommendations for each machine."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
import json
from math import isfinite, sqrt
from statistics import median

from .resource_domain import (
    CapacityAction,
    CapacityLevel,
    CapacityRecommendation,
    MachineResourceConfig,
    ResourceMode,
    ResourceTelemetry,
)


@dataclass(frozen=True, slots=True)
class _LevelEvidence:
    level: CapacityLevel
    samples: int
    throughput: float
    throughput_lower: float
    throughput_upper: float
    maximum_temperature: float
    minimum_memory_available: int
    maximum_swap_used: int
    maximum_error_rate: float
    all_stable: bool


class ResourceController:
    """Recommend capacity without starting workers or changing CPU frequency.

    The host supplies authorized levels and truthful telemetry. Recommendations
    affect future dispatch capacity only after a separate host actuator accepts
    them. No unobserved level is selected for a performance-driven increase.
    """

    version = "fada-rc/0.1"

    def __init__(self, config: MachineResourceConfig) -> None:
        self.config = config

    def recommend(
        self,
        current_level_id: str,
        samples: list[ResourceTelemetry],
        *,
        now: float,
        last_capacity_change_at: float | None = None,
    ) -> CapacityRecommendation:
        if not isfinite(now) or now < 0:
            raise ValueError("current time must be finite and non-negative")
        if last_capacity_change_at is not None and (
            not isfinite(last_capacity_change_at)
            or last_capacity_change_at < 0
            or last_capacity_change_at > now
        ):
            raise ValueError("last capacity change time must be between zero and now")
        current = self.config.level(current_level_id)
        if self.config.mode is ResourceMode.DISABLED:
            return self._result(
                current, current, CapacityAction.KEEP, "controller_disabled", 1.0, None
            )
        if not samples:
            return self._fallback(current, "telemetry_missing", None)
        if len({sample.observation_id for sample in samples}) != len(samples):
            return self._fallback(current, "duplicate_observation_id", None)
        if any(sample.machine_id != self.config.machine_id for sample in samples):
            return self._fallback(current, "telemetry_machine_mismatch", None)
        try:
            for sample in samples:
                self.config.level(sample.level_id)
        except ValueError:
            return self._fallback(current, "telemetry_level_not_authorized", None)

        latest = max(samples, key=lambda sample: (sample.observed_at, sample.observation_id))
        if latest.observed_at > now:
            return self._fallback(current, "telemetry_from_future", latest)
        if now - latest.observed_at > self.config.telemetry_max_age_seconds:
            return self._fallback(current, "telemetry_stale", latest)
        if latest.level_id != current.level_id:
            return self._fallback(current, "current_level_mismatch", latest)
        if (
            latest.active_workers != current.workers
            or latest.effective_core_clock_hz > current.core_clock_hz
        ):
            return self._fallback(current, "current_setting_mismatch", latest)

        window = [
            sample
            for sample in samples
            if 0 <= now - sample.observed_at <= self.config.observation_window_seconds
        ]
        evidence = self._evidence(window)
        temperature_rise = self._temperature_rise(latest, window)

        if latest.temperature_celsius >= self.config.thermal_critical_celsius:
            target = self._critical_target(current)
            if target.level_id == current.level_id:
                return self._fallback(
                    current,
                    "critical_temperature_no_safer_level",
                    latest,
                    temperature_rise=temperature_rise,
                )
            return self._result(
                current,
                target,
                CapacityAction.EMERGENCY_DECREASE,
                "critical_temperature",
                self._confidence(evidence.get(target.level_id)),
                latest,
                temperature_rise=temperature_rise,
            )

        pressure_reason = self._pressure_reason(latest)
        if (
            pressure_reason is None
            and self.config.maximum_temperature_rise_celsius_per_second is not None
            and temperature_rise is not None
            and temperature_rise
            > self.config.maximum_temperature_rise_celsius_per_second
        ):
            pressure_reason = "temperature_rise_limit_exceeded"
        if pressure_reason is not None:
            target = self._best_reduction(current, evidence, require_thermal_safe=True)
            if target.level_id == current.level_id:
                return self._fallback(
                    current,
                    f"{pressure_reason}_no_safer_level",
                    latest,
                    temperature_rise=temperature_rise,
                )
            return self._result(
                current,
                target,
                self._action(current, target),
                pressure_reason,
                self._confidence(evidence.get(target.level_id)),
                latest,
                target_evidence=evidence.get(target.level_id),
                temperature_rise=temperature_rise,
            )

        if latest.temperature_celsius >= self.config.thermal_warning_celsius:
            target = self._best_reduction(current, evidence, require_thermal_safe=True)
            if target.level_id == current.level_id:
                return self._fallback(
                    current,
                    "thermal_warning_no_safer_level",
                    latest,
                    temperature_rise=temperature_rise,
                )
            target_evidence = evidence.get(target.level_id)
            if self._qualified(target_evidence):
                reason = "thermal_warning_empirical_best_reduction"
            elif (
                target.workers < current.workers
                and target.core_clock_hz >= current.core_clock_hz
            ):
                reason = "thermal_warning_reduce_workers_first"
            else:
                reason = "thermal_warning_conservative_reduction"
            return self._result(
                current,
                target,
                self._action(current, target),
                reason,
                self._confidence(target_evidence),
                latest,
                target_evidence=target_evidence,
                temperature_rise=temperature_rise,
            )

        cooldown = (
            last_capacity_change_at is not None
            and now - last_capacity_change_at < self.config.cooldown_seconds
        )
        if cooldown:
            return self._result(
                current,
                current,
                CapacityAction.KEEP,
                "capacity_change_cooldown",
                1.0,
                latest,
                temperature_rise=temperature_rise,
            )

        recovery_limit = (
            self.config.thermal_warning_celsius
            - self.config.thermal_hysteresis_celsius
        )
        if latest.temperature_celsius > recovery_limit:
            return self._result(
                current,
                current,
                CapacityAction.KEEP,
                "thermal_recovery_hysteresis",
                1.0,
                latest,
                temperature_rise=temperature_rise,
            )

        if (
            self.config.maximum_temperature_rise_celsius_per_second is not None
            and temperature_rise is None
        ):
            return self._result(
                current,
                current,
                CapacityAction.KEEP,
                "temperature_rise_unavailable",
                0.0,
                latest,
            )

        current_evidence = evidence.get(current.level_id)
        if not self._qualified(current_evidence):
            return self._result(
                current,
                current,
                CapacityAction.KEEP,
                "insufficient_current_level_observations",
                self._confidence(current_evidence),
                latest,
                target_evidence=current_evidence,
                temperature_rise=temperature_rise,
            )

        candidates = [
            item
            for item in evidence.values()
            if self._qualified(item) and self._safe(item)
        ]
        if not candidates:
            return self._fallback(
                current,
                "no_safe_observed_capacity_level",
                latest,
                temperature_rise=temperature_rise,
            )
        best = max(
            candidates,
            key=lambda item: (
                item.throughput_lower,
                item.throughput,
                item.level.core_clock_hz,
                -item.level.workers,
                item.level.level_id,
            ),
        )
        gain = (best.throughput_lower - current_evidence.throughput_upper) / max(
            current_evidence.throughput_upper, 1e-12
        )
        if (
            best.level.level_id == current.level_id
            or best.throughput_lower <= current_evidence.throughput_upper
            or gain < self.config.minimum_throughput_gain_ratio
        ):
            return self._result(
                current,
                current,
                CapacityAction.KEEP,
                "no_significant_throughput_gain",
                1.0,
                latest,
                target_evidence=current_evidence,
                temperature_rise=temperature_rise,
            )
        target = self._one_step_toward(current, best.level)
        target_evidence = evidence.get(target.level_id)
        if not self._qualified(target_evidence) or not self._safe(target_evidence):
            return self._result(
                current,
                current,
                CapacityAction.KEEP,
                "adjacent_level_lacks_safe_observations",
                self._confidence(target_evidence),
                latest,
                target_evidence=target_evidence,
                temperature_rise=temperature_rise,
            )
        return self._result(
            current,
            target,
            self._action(current, target),
            "observed_throughput_gain",
            self._confidence(target_evidence),
            latest,
            target_evidence=target_evidence,
            temperature_rise=temperature_rise,
        )

    def _evidence(
        self, samples: list[ResourceTelemetry]
    ) -> dict[str, _LevelEvidence]:
        grouped: dict[str, list[ResourceTelemetry]] = defaultdict(list)
        for sample in samples:
            grouped[sample.level_id].append(sample)
        result: dict[str, _LevelEvidence] = {}
        for level_id, items in grouped.items():
            throughputs = [item.throughput_tasks_per_second for item in items]
            throughput = median(throughputs)
            deviations = [abs(value - throughput) for value in throughputs]
            robust_standard_error = (
                1.4826 * median(deviations) / sqrt(len(throughputs))
            )
            margin = (
                self.config.throughput_uncertainty_multiplier
                * robust_standard_error
            )
            result[level_id] = _LevelEvidence(
                level=self.config.level(level_id),
                samples=len(items),
                throughput=throughput,
                throughput_lower=max(0.0, throughput - margin),
                throughput_upper=throughput + margin,
                maximum_temperature=max(item.temperature_celsius for item in items),
                minimum_memory_available=min(
                    item.memory_available_bytes for item in items
                ),
                maximum_swap_used=max(item.swap_used_bytes for item in items),
                maximum_error_rate=max(item.error_rate for item in items),
                all_stable=all(
                    item.stable and not item.thermal_throttled for item in items
                ),
            )
        return result

    @staticmethod
    def _temperature_rise(
        latest: ResourceTelemetry, samples: list[ResourceTelemetry]
    ) -> float | None:
        previous = [
            sample
            for sample in samples
            if sample.level_id == latest.level_id
            and sample.observed_at < latest.observed_at
        ]
        if not previous:
            return None
        prior = max(
            previous,
            key=lambda sample: (sample.observed_at, sample.observation_id),
        )
        elapsed = latest.observed_at - prior.observed_at
        return (latest.temperature_celsius - prior.temperature_celsius) / elapsed

    def _qualified(self, evidence: _LevelEvidence | None) -> bool:
        return bool(
            evidence
            and evidence.samples >= self.config.minimum_samples_per_level
        )

    def _safe(self, evidence: _LevelEvidence) -> bool:
        return (
            evidence.maximum_temperature < self.config.thermal_warning_celsius
            and evidence.minimum_memory_available >= self.config.memory_reserve_bytes
            and evidence.maximum_swap_used <= self.config.maximum_swap_used_bytes
            and evidence.maximum_error_rate <= self.config.maximum_error_rate
            and evidence.all_stable
        )

    def _pressure_reason(self, latest: ResourceTelemetry) -> str | None:
        if latest.memory_available_bytes < self.config.memory_reserve_bytes:
            return "memory_reserve_violated"
        if latest.swap_used_bytes > self.config.maximum_swap_used_bytes:
            return "swap_limit_violated"
        if latest.error_rate > self.config.maximum_error_rate:
            return "error_rate_limit_violated"
        if latest.thermal_throttled:
            return "thermal_throttling_detected"
        if not latest.stable:
            return "machine_unstable"
        return None

    def _adjacent_reductions(self, current: CapacityLevel) -> list[CapacityLevel]:
        lower_workers = sorted(
            (
                level
                for level in self.config.authorized_levels
                if level.workers < current.workers
                and level.core_clock_hz == current.core_clock_hz
            ),
            key=lambda level: level.workers,
            reverse=True,
        )
        lower_clock = sorted(
            (
                level
                for level in self.config.authorized_levels
                if level.workers == current.workers
                and level.core_clock_hz < current.core_clock_hz
            ),
            key=lambda level: level.core_clock_hz,
            reverse=True,
        )
        candidates = lower_workers[:1] + lower_clock[:1]
        if candidates:
            return candidates
        lower_load = sorted(
            (
                level
                for level in self.config.authorized_levels
                if level.load_proxy < current.load_proxy
            ),
            key=lambda level: (level.load_proxy, level.core_clock_hz),
            reverse=True,
        )
        return lower_load[:1]

    def _best_reduction(
        self,
        current: CapacityLevel,
        evidence: dict[str, _LevelEvidence],
        *,
        require_thermal_safe: bool,
    ) -> CapacityLevel:
        candidates = self._adjacent_reductions(current)
        empirical = [
            item
            for level in candidates
            if self._qualified(item := evidence.get(level.level_id))
            and (not require_thermal_safe or self._safe(item))
        ]
        if empirical:
            return max(
                empirical,
                key=lambda item: (
                    item.throughput_lower,
                    item.throughput,
                    item.level.core_clock_hz,
                    -item.level.workers,
                    item.level.level_id,
                ),
            ).level
        thread_reductions = [
            level
            for level in candidates
            if level.workers < current.workers
            and level.core_clock_hz >= current.core_clock_hz
        ]
        if thread_reductions:
            return max(
                thread_reductions,
                key=lambda level: (level.workers, level.core_clock_hz, level.level_id),
            )
        return candidates[0] if candidates else current

    def _critical_target(self, current: CapacityLevel) -> CapacityLevel:
        lower = [
            level
            for level in self.config.authorized_levels
            if level.load_proxy < current.load_proxy
        ]
        if not lower:
            return current
        return min(
            lower,
            key=lambda level: (
                level.load_proxy,
                -level.core_clock_hz,
                level.workers,
                level.level_id,
            ),
        )

    def _one_step_toward(
        self, current: CapacityLevel, desired: CapacityLevel
    ) -> CapacityLevel:
        ordered = sorted(
            self.config.authorized_levels,
            key=lambda level: (level.load_proxy, level.core_clock_hz, level.workers),
        )
        current_index = ordered.index(current)
        desired_index = ordered.index(desired)
        if desired_index > current_index:
            return ordered[current_index + 1]
        if desired_index < current_index:
            return ordered[current_index - 1]
        return current

    @staticmethod
    def _action(current: CapacityLevel, target: CapacityLevel) -> CapacityAction:
        worker_change = target.workers - current.workers
        clock_change = target.core_clock_hz - current.core_clock_hz
        if worker_change == 0 and clock_change == 0:
            return CapacityAction.KEEP
        if worker_change and clock_change:
            return CapacityAction.CHANGE_WORKERS_AND_CLOCK
        if worker_change > 0:
            return CapacityAction.INCREASE_WORKERS
        if worker_change < 0:
            return CapacityAction.DECREASE_WORKERS
        if clock_change > 0:
            return CapacityAction.INCREASE_CLOCK
        return CapacityAction.DECREASE_CLOCK

    def _confidence(self, evidence: _LevelEvidence | None) -> float:
        if evidence is None:
            return 0.0
        return min(1.0, evidence.samples / self.config.minimum_samples_per_level)

    def _fallback(
        self,
        current: CapacityLevel,
        reason: str,
        latest: ResourceTelemetry | None,
        *,
        temperature_rise: float | None = None,
    ) -> CapacityRecommendation:
        return self._result(
            current,
            current,
            CapacityAction.FALLBACK,
            reason,
            0.0,
            latest,
            temperature_rise=temperature_rise,
        )

    def _result(
        self,
        current: CapacityLevel,
        target: CapacityLevel,
        action: CapacityAction,
        reason: str,
        confidence: float,
        latest: ResourceTelemetry | None,
        *,
        target_evidence: _LevelEvidence | None = None,
        temperature_rise: float | None = None,
    ) -> CapacityRecommendation:
        observation_id = latest.observation_id if latest else None
        payload = json.dumps(
            {
                "action": action.value,
                "current": current.level_id,
                "machine": self.config.machine_id,
                "mode": self.config.mode.value,
                "observation": observation_id,
                "reason": reason,
                "target": target.level_id,
                "target_clock_hz": target.core_clock_hz,
                "target_workers": target.workers,
                "version": self.version,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return CapacityRecommendation(
            machine_id=self.config.machine_id,
            mode=self.config.mode,
            action=action,
            current_level_id=current.level_id,
            recommended_level_id=target.level_id,
            apply_allowed=(
                self.config.mode is ResourceMode.ACTIVE
                and action not in {CapacityAction.KEEP, CapacityAction.FALLBACK}
            ),
            reason=reason,
            confidence=confidence,
            observation_id=observation_id,
            idempotency_key=sha256(payload.encode("utf-8")).hexdigest(),
            controller_version=self.version,
            predicted_throughput_tasks_per_second=(
                target_evidence.throughput if target_evidence else None
            ),
            throughput_lower_bound=(
                target_evidence.throughput_lower if target_evidence else None
            ),
            throughput_upper_bound=(
                target_evidence.throughput_upper if target_evidence else None
            ),
            temperature_rise_celsius_per_second=temperature_rise,
        )
