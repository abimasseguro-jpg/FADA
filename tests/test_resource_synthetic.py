from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from resource_controller_synthetic import (
    SCENARIOS,
    TRACE_SCHEMA_VERSION,
    build_synthetic_resource_trace,
    trace_document,
)

from fada import ResourceController, replay_resource_telemetry


class SyntheticResourceTraceTests(unittest.TestCase):
    def test_same_seed_reproduces_exact_trace(self) -> None:
        first = build_synthetic_resource_trace("non_monotonic", 7)
        second = build_synthetic_resource_trace("non_monotonic", 7)
        self.assertEqual(first, second)

    def test_all_registered_scenarios_are_serializable_and_shadow_only(self) -> None:
        for scenario_id in SCENARIOS:
            with self.subTest(scenario_id=scenario_id):
                trace = build_synthetic_resource_trace(scenario_id, 0)
                document = trace_document(trace)
                self.assertEqual(document["schema_version"], TRACE_SCHEMA_VERSION)
                self.assertEqual(document["config"]["mode"], "shadow")
                json.dumps(document, sort_keys=True, allow_nan=False)

    def test_synthetic_replay_never_authorizes_application(self) -> None:
        for scenario_id in SCENARIOS:
            with self.subTest(scenario_id=scenario_id):
                trace = build_synthetic_resource_trace(scenario_id, 0)
                records = replay_resource_telemetry(
                    ResourceController(trace.config), list(trace.samples)
                )
                self.assertTrue(records)
                self.assertFalse(
                    any(record.recommendation.apply_allowed for record in records)
                )

    def test_invalid_generator_bounds_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_synthetic_resource_trace("unknown", 0)
        with self.assertRaises(ValueError):
            build_synthetic_resource_trace("non_monotonic", -1)
        with self.assertRaises(ValueError):
            build_synthetic_resource_trace("non_monotonic", 0, samples_per_level=1)


if __name__ == "__main__":
    unittest.main()
