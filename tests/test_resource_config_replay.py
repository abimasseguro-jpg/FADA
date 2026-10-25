from __future__ import annotations

import unittest

from fada import (
    CapacityLevel,
    MachineResourceConfig,
    ResourceConfigError,
    ResourceController,
    ResourceMode,
    ResourceTelemetry,
    machine_resource_config_from_dict,
    replay_resource_telemetry,
    summarize_resource_replay,
)


class ResourceConfigReplayTests(unittest.TestCase):
    def configuration_document(self):
        return {
            "schema_version": "fada-resource-config/v1",
            "machine_id": "node-a",
            "mode": "shadow",
            "authorized_levels": [
                {"level_id": "one", "workers": 1, "core_clock_hz": 100},
                {"level_id": "two", "workers": 2, "core_clock_hz": 100},
            ],
            "minimum_samples_per_level": 2,
            "maximum_temperature_rise_celsius_per_second": 1,
        }

    def test_configuration_loader_is_strict_and_preserves_disabled_authority(self) -> None:
        config = machine_resource_config_from_dict(self.configuration_document())
        self.assertEqual(config.mode, ResourceMode.SHADOW)
        self.assertEqual(config.level("two").workers, 2)

        invalid = self.configuration_document()
        invalid["unexpected"] = True
        with self.assertRaises(ResourceConfigError):
            machine_resource_config_from_dict(invalid)

    def test_unknown_schema_and_ambiguous_boolean_integer_are_rejected(self) -> None:
        invalid_version = self.configuration_document()
        invalid_version["schema_version"] = "future"
        with self.assertRaises(ResourceConfigError):
            machine_resource_config_from_dict(invalid_version)

        ambiguous = self.configuration_document()
        ambiguous["authorized_levels"][0]["workers"] = True
        with self.assertRaises(ResourceConfigError):
            machine_resource_config_from_dict(ambiguous)

    def test_replay_is_ordered_and_does_not_expose_future_samples(self) -> None:
        config = machine_resource_config_from_dict(self.configuration_document())
        level = config.level("one")

        def sample(observation_id: str, observed_at: float, temperature: float):
            return ResourceTelemetry(
                observation_id=observation_id,
                machine_id="node-a",
                observed_at=observed_at,
                level_id=level.level_id,
                active_workers=level.workers,
                effective_core_clock_hz=level.core_clock_hz,
                throughput_tasks_per_second=1,
                temperature_celsius=temperature,
                memory_available_bytes=1000,
                swap_used_bytes=0,
            )

        records = replay_resource_telemetry(
            ResourceController(config),
            [sample("later", 2, 72), sample("first", 1, 70)],
        )
        self.assertEqual([record.observation_id for record in records], ["first", "later"])
        self.assertEqual(
            records[0].recommendation.reason,
            "temperature_rise_unavailable",
        )
        self.assertIsNone(
            records[0].recommendation.temperature_rise_celsius_per_second
        )
        self.assertEqual(
            records[1].recommendation.temperature_rise_celsius_per_second, 2
        )

        summary = summarize_resource_replay(records)
        self.assertEqual(summary.observations, 2)
        self.assertEqual(summary.peak_temperature_celsius, 72)

    def test_replay_rejects_duplicate_observation_identity(self) -> None:
        level = CapacityLevel("one", 1, 100)
        config = MachineResourceConfig("node-a", (level,), mode=ResourceMode.SHADOW)
        sample = ResourceTelemetry(
            "same", "node-a", 1, "one", 1, 100, 1, 60, 1000, 0
        )
        with self.assertRaises(ValueError):
            replay_resource_telemetry(ResourceController(config), [sample, sample])


if __name__ == "__main__":
    unittest.main()
