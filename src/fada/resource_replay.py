"""Deterministic, side-effect-free temporal replay for Resource Controller."""

from __future__ import annotations

from dataclasses import dataclass

from .resource_control import ResourceController
from .resource_domain import (
    CapacityAction,
    CapacityRecommendation,
    ResourceTelemetry,
)


@dataclass(frozen=True, slots=True)
class ResourceReplayRecord:
    step: int
    observed_at: float
    observation_id: str
    observed_level_id: str
    observed_temperature_celsius: float
    recommendation: CapacityRecommendation


@dataclass(frozen=True, slots=True)
class ResourceReplaySummary:
    observations: int
    recommended_changes: int
    fallbacks: int
    peak_temperature_celsius: float | None
    maximum_temperature_rise_celsius_per_second: float | None
    action_counts: tuple[tuple[str, int], ...]


def replay_resource_telemetry(
    controller: ResourceController,
    samples: list[ResourceTelemetry],
) -> list[ResourceReplayRecord]:
    """Replay in event time without exposing future samples to a decision."""

    if len({sample.observation_id for sample in samples}) != len(samples):
        raise ValueError("replay observation ids must be unique")
    ordered = sorted(
        samples,
        key=lambda sample: (sample.observed_at, sample.observation_id),
    )
    history: list[ResourceTelemetry] = []
    records: list[ResourceReplayRecord] = []
    previous_level_id: str | None = None
    last_capacity_change_at: float | None = None
    for step, sample in enumerate(ordered):
        if previous_level_id is not None and sample.level_id != previous_level_id:
            last_capacity_change_at = sample.observed_at
        history.append(sample)
        recommendation = controller.recommend(
            sample.level_id,
            history,
            now=sample.observed_at,
            last_capacity_change_at=last_capacity_change_at,
        )
        records.append(
            ResourceReplayRecord(
                step=step,
                observed_at=sample.observed_at,
                observation_id=sample.observation_id,
                observed_level_id=sample.level_id,
                observed_temperature_celsius=sample.temperature_celsius,
                recommendation=recommendation,
            )
        )
        previous_level_id = sample.level_id
    return records


def summarize_resource_replay(
    records: list[ResourceReplayRecord],
) -> ResourceReplaySummary:
    counts: dict[str, int] = {}
    rises: list[float] = []
    temperatures: list[float] = []
    for record in records:
        recommendation = record.recommendation
        key = recommendation.action.value
        counts[key] = counts.get(key, 0) + 1
        temperatures.append(record.observed_temperature_celsius)
        if recommendation.temperature_rise_celsius_per_second is not None:
            rises.append(recommendation.temperature_rise_celsius_per_second)
    return ResourceReplaySummary(
        observations=len(records),
        recommended_changes=sum(
            count
            for action, count in counts.items()
            if action not in {CapacityAction.KEEP.value, CapacityAction.FALLBACK.value}
        ),
        fallbacks=counts.get(CapacityAction.FALLBACK.value, 0),
        peak_temperature_celsius=max(temperatures) if temperatures else None,
        maximum_temperature_rise_celsius_per_second=max(rises) if rises else None,
        action_counts=tuple(sorted(counts.items())),
    )
