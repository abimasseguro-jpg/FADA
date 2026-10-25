from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from run_cpu_live_shadow_service import SCHEMA_VERSION, atomic_json, load_config


class CpuLiveShadowServiceTests(unittest.TestCase):
    def test_production_configuration_has_no_application_channel(self) -> None:
        config = load_config(ROOT)
        self.assertEqual(config["schema_version"], SCHEMA_VERSION)
        self.assertEqual(config["mode"], "shadow")
        self.assertIsNone(config["application_channel"])
        self.assertEqual(config["remote_host"], "codex-acer")

    def test_atomic_state_replaces_complete_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "state.json"
            atomic_json(target, {"status": "running", "samples": 1})
            self.assertEqual(
                json.loads(target.read_text(encoding="utf-8")),
                {"status": "running", "samples": 1},
            )
            self.assertFalse(target.with_suffix(".json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
