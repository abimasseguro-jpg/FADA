"""Held-out, deterministic calibration metrics for duration estimates."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .estimation_v02 import DurationEstimate


CALIBRATION_METRICS_SCHEMA_VERSION = "fada-duration-calibration/v1"


@dataclass(frozen=True, slots=True)
class DurationFeedback:
    prediction_id: str
    predicted_at: float
    observed_at: float
    estimate: DurationEstimate
    completed_elapsed_seconds: float

    def __post_init__(self) -> None:
        if not self.prediction_id:
            raise ValueError("prediction identity must not be empty")
        if not all(isfinite(value) and value >= 0 for value in (self.predicted_at, self.observed_at)):
            raise ValueError("feedback times must be finite and non-negative")
        if self.predicted_at > self.observed_at:
            raise ValueError("prediction cannot follow its observed completion")
        if not isfinite(self.completed_elapsed_seconds) or self.completed_elapsed_seconds <= 0:
            raise ValueError("completed feedback duration must be finite and positive")


@dataclass(frozen=True, slots=True)
class CalibrationMetrics:
    feedback_count: int
    interval_coverage: float
    mean_absolute_relative_error: float
    p50_pinball_loss: float
    p95_pinball_loss: float
    evaluation_after: float
    schema_version: str = CALIBRATION_METRICS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != CALIBRATION_METRICS_SCHEMA_VERSION:
            raise ValueError("unsupported calibration metrics schema")
        if self.feedback_count <= 0:
            raise ValueError("calibration requires held-out feedback")
        if not isfinite(self.evaluation_after) or self.evaluation_after < 0:
            raise ValueError("evaluation cutoff must be finite and non-negative")
        if not 0 <= self.interval_coverage <= 1:
            raise ValueError("interval coverage must be in [0, 1]")
        for value in (
            self.mean_absolute_relative_error,
            self.p50_pinball_loss,
            self.p95_pinball_loss,
        ):
            if not isfinite(value) or value < 0:
                raise ValueError("calibration losses must be finite and non-negative")

def _pinball(observed: float, quantile: float, probability: float) -> float:
    error = observed - quantile
    return probability * error if error >= 0 else (probability - 1.0) * error


def calibrate_held_out(
    feedback: list[DurationFeedback], *, evaluation_after: float
) -> CalibrationMetrics:
    """Score only feedback that occurs strictly after the frozen cutoff."""

    if not isfinite(evaluation_after) or evaluation_after < 0:
        raise ValueError("evaluation cutoff must be finite and non-negative")
    if not feedback:
        raise ValueError("calibration requires feedback")
    identities = [item.prediction_id for item in feedback]
    if len(identities) != len(set(identities)):
        raise ValueError("feedback identities must be unique")
    if any(item.observed_at <= evaluation_after for item in feedback):
        raise ValueError("calibration feedback must be held out after the cutoff")

    covered = sum(
        item.estimate.lower_seconds <= item.completed_elapsed_seconds <= item.estimate.upper_seconds
        for item in feedback
    )
    absolute_relative = [
        abs(item.estimate.point_seconds - item.completed_elapsed_seconds) / item.completed_elapsed_seconds
        for item in feedback
    ]
    p50_losses = [_pinball(item.completed_elapsed_seconds, item.estimate.p50_seconds, 0.5) for item in feedback]
    p95_losses = [_pinball(item.completed_elapsed_seconds, item.estimate.p95_seconds, 0.95) for item in feedback]
    count = len(feedback)
    return CalibrationMetrics(
        feedback_count=count,
        interval_coverage=covered / count,
        mean_absolute_relative_error=sum(absolute_relative) / count,
        p50_pinball_loss=sum(p50_losses) / count,
        p95_pinball_loss=sum(p95_losses) / count,
        evaluation_after=evaluation_after,
    )
