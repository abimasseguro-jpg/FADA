"""Explicit, reversible selection of a scheduling policy."""

from __future__ import annotations

from dataclasses import dataclass

from .policy import HybridPolicy


@dataclass(slots=True)
class PolicyController:
    """Keep policy promotion reversible without touching queue state.

    The host executor owns persistence and dispatch.  This controller only keeps
    the active and immediately previous policy, so rollback cannot rewrite work
    that has already been leased or completed.
    """

    active: HybridPolicy
    previous: HybridPolicy | None = None

    def promote(self, policy: HybridPolicy) -> None:
        if policy.version == self.active.version:
            raise ValueError("new policy version must differ from active version")
        self.previous = self.active
        self.active = policy

    def rollback(self) -> HybridPolicy:
        if self.previous is None:
            raise RuntimeError("no previous policy available for rollback")
        rolled_back = self.previous
        self.previous = self.active
        self.active = rolled_back
        return self.active
