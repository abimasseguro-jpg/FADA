"""Bounded-search implementation of the plan-guarded FADA-HS policy."""

from __future__ import annotations

from dataclasses import dataclass

from .policy_v03 import PlanGuardedHybridPolicy


@dataclass(slots=True)
class BoundedPlanGuardedHybridPolicy(PlanGuardedHybridPolicy):
    """0.4 preserves the 0.3 guard while bounding the candidate projection."""

    version: str = "fada-hs/0.4"
    candidate_window: int = 8
    projection_limit: int = 24
