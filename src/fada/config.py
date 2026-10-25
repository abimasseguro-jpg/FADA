"""Strict JSON configuration loading for the Resource Controller."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .resource_domain import CapacityLevel, MachineResourceConfig, ResourceMode


RESOURCE_CONFIG_SCHEMA_VERSION = "fada-resource-config/v1"


class ResourceConfigError(ValueError):
    """Configuration is malformed, ambiguous, or uses an unsupported schema."""


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ResourceConfigError(f"{name} must be an object")
    return value


def _exact_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ResourceConfigError(f"{name} must be an integer")
    return value


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ResourceConfigError(f"{name} must be a number")
    return float(value)


def machine_resource_config_from_dict(
    document: Mapping[str, Any],
) -> MachineResourceConfig:
    data = dict(_mapping(document, "resource configuration"))
    schema_version = data.pop("schema_version", None)
    if schema_version != RESOURCE_CONFIG_SCHEMA_VERSION:
        raise ResourceConfigError(
            f"unsupported resource configuration schema: {schema_version!r}"
        )

    required = {"machine_id", "mode", "authorized_levels"}
    missing = sorted(required - data.keys())
    allowed = required | {
        "minimum_samples_per_level",
        "observation_window_seconds",
        "telemetry_max_age_seconds",
        "cooldown_seconds",
        "minimum_throughput_gain_ratio",
        "memory_reserve_bytes",
        "maximum_swap_used_bytes",
        "maximum_error_rate",
        "thermal_warning_celsius",
        "thermal_critical_celsius",
        "thermal_hysteresis_celsius",
        "maximum_temperature_rise_celsius_per_second",
        "throughput_uncertainty_multiplier",
    }
    unknown = sorted(data.keys() - allowed)
    if missing:
        raise ResourceConfigError(f"missing configuration fields: {', '.join(missing)}")
    if unknown:
        raise ResourceConfigError(f"unknown configuration fields: {', '.join(unknown)}")

    raw_levels = data.pop("authorized_levels")
    if not isinstance(raw_levels, list) or not raw_levels:
        raise ResourceConfigError("authorized_levels must be a non-empty array")
    levels: list[CapacityLevel] = []
    for index, raw_level in enumerate(raw_levels):
        level = dict(_mapping(raw_level, f"authorized_levels[{index}]"))
        level_unknown = sorted(level.keys() - {"level_id", "workers", "core_clock_hz"})
        level_missing = sorted(
            {"level_id", "workers", "core_clock_hz"} - level.keys()
        )
        if level_missing or level_unknown:
            raise ResourceConfigError(
                f"invalid authorized_levels[{index}] fields; "
                f"missing={level_missing}, unknown={level_unknown}"
            )
        if not isinstance(level["level_id"], str):
            raise ResourceConfigError(
                f"authorized_levels[{index}].level_id must be a string"
            )
        try:
            levels.append(
                CapacityLevel(
                    level_id=level["level_id"],
                    workers=_exact_int(
                        level["workers"], f"authorized_levels[{index}].workers"
                    ),
                    core_clock_hz=_exact_int(
                        level["core_clock_hz"],
                        f"authorized_levels[{index}].core_clock_hz",
                    ),
                )
            )
        except ValueError as error:
            raise ResourceConfigError(str(error)) from error

    try:
        mode = ResourceMode(data.pop("mode"))
    except (TypeError, ValueError) as error:
        raise ResourceConfigError("mode is not supported") from error
    machine_id = data.pop("machine_id")
    if not isinstance(machine_id, str):
        raise ResourceConfigError("machine_id must be a string")

    integer_fields = {
        "minimum_samples_per_level",
        "memory_reserve_bytes",
        "maximum_swap_used_bytes",
    }
    nullable_number_fields = {"maximum_temperature_rise_celsius_per_second"}
    normalized: dict[str, Any] = {}
    for name, value in data.items():
        if name in integer_fields:
            normalized[name] = _exact_int(value, name)
        elif name in nullable_number_fields and value is None:
            normalized[name] = None
        else:
            normalized[name] = _number(value, name)
    try:
        return MachineResourceConfig(
            machine_id=machine_id,
            authorized_levels=tuple(levels),
            mode=mode,
            **normalized,
        )
    except (TypeError, ValueError) as error:
        raise ResourceConfigError(str(error)) from error


def load_machine_resource_config(path: str | Path) -> MachineResourceConfig:
    source = Path(path)
    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ResourceConfigError(f"cannot load resource configuration: {source}") from error
    return machine_resource_config_from_dict(_mapping(document, "resource configuration"))
