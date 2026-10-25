from __future__ import annotations

import unittest

from fada import (
    CapacityAction,
    CapacityLevel,
    MachineResourceConfig,
    NoOpCapacityActuator,
    ResourceController,
    ResourceMode,
    ResourceTelemetry,
)


class ResourceControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.levels = (
            CapacityLevel("2t-4g", workers=2, core_clock_hz=4_000_000_000),
            CapacityLevel("4t-3g", workers=4, core_clock_hz=3_000_000_000),
            CapacityLevel("4t-4g", workers=4, core_clock_hz=4_000_000_000),
            CapacityLevel("8t-4g", workers=8, core_clock_hz=4_000_000_000),
        )

    def config(self, mode: ResourceMode = ResourceMode.ADVISORY, **changes):
        values = {
            "machine_id": "node-a",
            "authorized_levels": self.levels,
            "mode": mode,
            "minimum_samples_per_level": 2,
            "observation_window_seconds": 100,
            "telemetry_max_age_seconds": 20,
            "cooldown_seconds": 30,
            "minimum_throughput_gain_ratio": 0.05,
            "memory_reserve_bytes": 100,
            "maximum_swap_used_bytes": 0,
            "maximum_error_rate": 0.01,
            "thermal_warning_celsius": 80,
            "thermal_critical_celsius": 90,
            "thermal_hysteresis_celsius": 4,
            "maximum_temperature_rise_celsius_per_second": 0.5,
            "throughput_uncertainty_multiplier": 2,
        }
        values.update(changes)
        return MachineResourceConfig(**values)

    @staticmethod
    def sample(
        observation_id: str,
        level: CapacityLevel,
        *,
        at: float,
        throughput: float,
        temperature: float = 60,
        memory: int = 1000,
        swap: int = 0,
        error_rate: float = 0,
        stable: bool = True,
    ) -> ResourceTelemetry:
        return ResourceTelemetry(
            observation_id=observation_id,
            machine_id="node-a",
            observed_at=at,
            level_id=level.level_id,
            active_workers=level.workers,
            effective_core_clock_hz=level.core_clock_hz,
            throughput_tasks_per_second=throughput,
            temperature_celsius=temperature,
            memory_available_bytes=memory,
            swap_used_bytes=swap,
            error_rate=error_rate,
            stable=stable,
        )

    def evidence(self, level: CapacityLevel, throughput: float, start: int):
        return [
            self.sample(f"o-{start}", level, at=98, throughput=throughput),
            self.sample(f"o-{start + 1}", level, at=99, throughput=throughput),
        ]

    def test_disabled_mode_is_inert_without_telemetry(self) -> None:
        recommendation = ResourceController(
            self.config(ResourceMode.DISABLED)
        ).recommend("4t-4g", [], now=100)
        self.assertEqual(recommendation.action, CapacityAction.KEEP)
        self.assertFalse(recommendation.apply_allowed)

    def test_missing_and_stale_telemetry_fail_closed(self) -> None:
        controller = ResourceController(self.config())
        missing = controller.recommend("4t-4g", [], now=100)
        stale = controller.recommend(
            "4t-4g",
            [self.sample("old", self.levels[2], at=1, throughput=1)],
            now=100,
        )
        self.assertEqual(missing.action, CapacityAction.FALLBACK)
        self.assertEqual(stale.reason, "telemetry_stale")

    def test_best_observed_throughput_wins_not_most_workers(self) -> None:
        samples = (
            self.evidence(self.levels[1], 9, 10)
            + self.evidence(self.levels[2], 10, 20)
            + self.evidence(self.levels[3], 8, 30)
        )
        recommendation = ResourceController(self.config()).recommend(
            "8t-4g", samples, now=100
        )
        self.assertEqual(recommendation.recommended_level_id, "4t-4g")
        self.assertEqual(recommendation.action, CapacityAction.DECREASE_WORKERS)

    def test_unobserved_level_is_never_a_performance_increase(self) -> None:
        samples = (
            self.evidence(self.levels[0], 5, 10)
            + self.evidence(self.levels[2], 10, 20)
            + [self.sample("current", self.levels[0], at=100, throughput=5)]
        )
        recommendation = ResourceController(self.config()).recommend(
            "2t-4g", samples, now=100
        )
        self.assertEqual(recommendation.action, CapacityAction.KEEP)
        self.assertEqual(
            recommendation.reason, "adjacent_level_lacks_safe_observations"
        )

    def test_thermal_warning_prefers_fewer_workers_without_comparison(self) -> None:
        current = self.levels[2]
        hot = self.sample(
            "hot", current, at=100, throughput=10, temperature=82
        )
        recommendation = ResourceController(self.config()).recommend(
            current.level_id, [hot], now=100
        )
        self.assertEqual(recommendation.recommended_level_id, "2t-4g")
        self.assertEqual(recommendation.action, CapacityAction.DECREASE_WORKERS)
        self.assertEqual(recommendation.reason, "thermal_warning_reduce_workers_first")

    def test_thermal_warning_compares_threads_against_clock_empirically(self) -> None:
        current = self.levels[2]
        samples = (
            self.evidence(self.levels[0], 7, 10)
            + self.evidence(self.levels[1], 9, 20)
            + [self.sample("hot", current, at=100, throughput=10, temperature=82)]
        )
        recommendation = ResourceController(self.config()).recommend(
            current.level_id, samples, now=100
        )
        self.assertEqual(recommendation.recommended_level_id, "4t-3g")
        self.assertEqual(recommendation.action, CapacityAction.DECREASE_CLOCK)
        self.assertEqual(
            recommendation.reason, "thermal_warning_empirical_best_reduction"
        )

    def test_clock_is_tiebreaker_for_equally_fast_safe_reductions(self) -> None:
        current = self.levels[2]
        samples = (
            self.evidence(self.levels[0], 9, 10)
            + self.evidence(self.levels[1], 9, 20)
            + [self.sample("hot", current, at=100, throughput=10, temperature=82)]
        )
        recommendation = ResourceController(self.config()).recommend(
            current.level_id, samples, now=100
        )
        self.assertEqual(recommendation.recommended_level_id, "2t-4g")

    def test_critical_temperature_bypasses_cooldown(self) -> None:
        current = self.levels[3]
        hot = self.sample(
            "critical", current, at=100, throughput=10, temperature=95
        )
        recommendation = ResourceController(self.config()).recommend(
            current.level_id,
            [hot],
            now=100,
            last_capacity_change_at=99,
        )
        self.assertEqual(recommendation.action, CapacityAction.EMERGENCY_DECREASE)
        self.assertEqual(recommendation.recommended_level_id, "2t-4g")

    def test_cooldown_and_thermal_hysteresis_prevent_oscillation(self) -> None:
        current = self.levels[2]
        observations = self.evidence(current, 10, 10)
        cooldown = ResourceController(self.config()).recommend(
            current.level_id,
            observations,
            now=100,
            last_capacity_change_at=90,
        )
        warm = self.sample("warm", current, at=100, throughput=10, temperature=78)
        hysteresis = ResourceController(self.config()).recommend(
            current.level_id, [warm], now=100
        )
        self.assertEqual(cooldown.reason, "capacity_change_cooldown")
        self.assertEqual(hysteresis.reason, "thermal_recovery_hysteresis")

    def test_pressure_reduces_future_capacity(self) -> None:
        current = self.levels[2]
        low_memory = self.sample(
            "memory", current, at=100, throughput=10, memory=50
        )
        recommendation = ResourceController(self.config()).recommend(
            current.level_id, [low_memory], now=100
        )
        self.assertEqual(recommendation.action, CapacityAction.DECREASE_WORKERS)
        self.assertEqual(recommendation.reason, "memory_reserve_violated")

    def test_fast_temperature_rise_reduces_before_warning_limit(self) -> None:
        current = self.levels[2]
        samples = [
            self.sample("before", current, at=99, throughput=10, temperature=70),
            self.sample("rising", current, at=100, throughput=10, temperature=75),
        ]
        recommendation = ResourceController(self.config()).recommend(
            current.level_id, samples, now=100
        )
        self.assertEqual(recommendation.action, CapacityAction.DECREASE_WORKERS)
        self.assertEqual(recommendation.reason, "temperature_rise_limit_exceeded")
        self.assertEqual(recommendation.temperature_rise_celsius_per_second, 5)

    def test_missing_temperature_rate_blocks_performance_adaptation(self) -> None:
        current = self.levels[0]
        only = self.sample("only", current, at=100, throughput=8)
        recommendation = ResourceController(
            self.config(minimum_samples_per_level=1)
        ).recommend(current.level_id, [only], now=100)
        self.assertEqual(recommendation.action, CapacityAction.KEEP)
        self.assertEqual(recommendation.reason, "temperature_rise_unavailable")

    def test_uncertainty_blocks_noisy_apparent_gain(self) -> None:
        current = self.levels[0]
        candidate = self.levels[1]
        samples = [
            self.sample("current-1", current, at=97, throughput=8),
            self.sample("candidate-1", candidate, at=97, throughput=5),
            self.sample("candidate-2", candidate, at=98, throughput=15),
            self.sample("current-2", current, at=99, throughput=8),
            self.sample("current-now", current, at=100, throughput=8),
        ]
        recommendation = ResourceController(self.config()).recommend(
            current.level_id, samples, now=100
        )
        self.assertEqual(recommendation.action, CapacityAction.KEEP)
        self.assertEqual(recommendation.reason, "no_significant_throughput_gain")

    def test_only_active_mode_marks_a_change_as_applicable(self) -> None:
        current = self.levels[2]
        hot = self.sample("hot", current, at=100, throughput=10, temperature=82)
        advisory = ResourceController(self.config(ResourceMode.ADVISORY)).recommend(
            current.level_id, [hot], now=100
        )
        active = ResourceController(self.config(ResourceMode.ACTIVE)).recommend(
            current.level_id, [hot], now=100
        )
        repeated = ResourceController(self.config(ResourceMode.ADVISORY)).recommend(
            current.level_id, [hot], now=100
        )
        self.assertFalse(advisory.apply_allowed)
        self.assertTrue(active.apply_allowed)
        self.assertEqual(advisory.idempotency_key, repeated.idempotency_key)

    def test_noop_actuator_never_accepts_a_change(self) -> None:
        current = self.levels[2]
        hot = self.sample("hot", current, at=100, throughput=10, temperature=82)
        recommendation = ResourceController(
            self.config(ResourceMode.ACTIVE)
        ).recommend(current.level_id, [hot], now=100)
        receipt = NoOpCapacityActuator().request_capacity(recommendation)
        self.assertFalse(receipt.accepted)
        self.assertEqual(receipt.observed_level_id, current.level_id)

    def test_configuration_rejects_duplicate_or_invalid_levels(self) -> None:
        with self.assertRaises(ValueError):
            MachineResourceConfig(
                machine_id="node-a",
                authorized_levels=(self.levels[0], self.levels[0]),
            )
        with self.assertRaises(ValueError):
            CapacityLevel("invalid", workers=0, core_clock_hz=1)


if __name__ == "__main__":
    unittest.main()
