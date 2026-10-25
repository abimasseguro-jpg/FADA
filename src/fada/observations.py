"""Versioned, side-effect-free execution observations for FADA estimators.

An observation records what happened without treating a failure, interruption,
or limit-censored run as a completed duration.  This module deliberately owns
no queue, worker, or persistence channel.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite


DURATION_OBSERVATION_SCHEMA_VERSION = "fada-duration-observation/v1"


class ExecutionOutcome(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    REQUEUED = "requeued"
    CENSORED = "censored"


@dataclass(frozen=True, slots=True)
class DurationObservation:
    """One immutable execution observation with explicit outcome semantics."""

    observation_id: str
    scenario: str
    machine_id: str
    backend: str
    hardware_profile: str
    active_workers: int
    observed_at: float
    outcome: ExecutionOutcome
    elapsed_seconds: float | None = None
    censor_limit_seconds: float | None = None
    reason: str | None = None
    schema_version: str = DURATION_OBSERVATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != DURATION_OBSERVATION_SCHEMA_VERSION:
            raise ValueError("unsupported duration observation schema")
        if not all(
            isinstance(value, str) and value
            for value in (
                self.observation_id,
                self.scenario,
                self.machine_id,
                self.backend,
                self.hardware_profile,
            )
        ):
            raise ValueError("observation identities must not be empty")
        if isinstance(self.active_workers, bool) or not isinstance(self.active_workers, int) or self.active_workers <= 0:
            raise ValueError("active workers must be a positive integer")
        if not isfinite(self.observed_at) or self.observed_at < 0:
            raise ValueError("observation time must be finite and non-negative")
        if not isinstance(self.outcome, ExecutionOutcome):
            raise TypeError("outcome must be an ExecutionOutcome")
        if self.elapsed_seconds is not None and (
            not isfinite(self.elapsed_seconds) or self.elapsed_seconds < 0
        ):
            raise ValueError("elapsed seconds must be finite and non-negative")
        if self.censor_limit_seconds is not None and (
            not isfinite(self.censor_limit_seconds) or self.censor_limit_seconds <= 0
        ):
            raise ValueError("censor limit must be finite and positive")

        if self.outcome is ExecutionOutcome.COMPLETED:
            if self.elapsed_seconds is None or self.elapsed_seconds <= 0:
                raise ValueError("completed observation requires a positive duration")
            if self.censor_limit_seconds is not None or self.reason is not None:
                raise ValueError("completed observation cannot carry censoring or failure metadata")
        elif self.outcome is ExecutionOutcome.CENSORED:
            if self.censor_limit_seconds is None or not self.reason:
                raise ValueError("censored observation requires a limit and reason")
        else:
            if not self.reason:
                raise ValueError("failed, interrupted or requeued observation requires a reason")
            if self.censor_limit_seconds is not None:
                raise ValueError("only censored observations may carry a censor limit")

    @property
    def completed_duration_seconds(self) -> float | None:
        """Return a training duration only for genuinely completed executions."""

        if self.outcome is ExecutionOutcome.COMPLETED:
            return self.elapsed_seconds
        return None
