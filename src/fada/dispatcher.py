"""Active FADA dispatcher boundary with fail-closed queue semantics."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping, Protocol

from .domain import Decision, Task, WorkerSlot
from .estimation import ScenarioEstimator
from .policy_v04 import BoundedPlanGuardedHybridPolicy
from .policy_cost_progress import CostWeightedProgressPolicy
from .policy_scenario_cohort import (
    ConcurrentScenarioPolicy, CostBalancedScenarioPolicy,
    ScenarioStatus, ScenarioWorkStatus,
)
from .adaptive import AdaptiveWatchdog, adaptive_assignments


class QueueBackend(Protocol):
    def claim(self, task_id: str, worker_id: str, idempotency_key: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class DispatchReceipt:
    decision: Decision
    claimed: bool
    idempotency_key: str
    dispatcher_version: str = "fada-dispatcher/0.1"


class FADADispatcher:
    """Turn a FADA decision into one atomic queue claim.

    The queue adapter owns persistence/leases.  FADA never mutates a queue
    before a policy decision, never falls back silently, and refuses a claim
    when the selected worker is not present in the supplied snapshot.
    """

    version = "fada-dispatcher/0.1"

    def __init__(self, policy: BoundedPlanGuardedHybridPolicy | CostWeightedProgressPolicy | ConcurrentScenarioPolicy | CostBalancedScenarioPolicy | None = None) -> None:
        self.policy = policy or BoundedPlanGuardedHybridPolicy()

    @staticmethod
    def plan_adaptive(pending: list[str], active: Mapping[str, object],
                      completed: list[str], available: list[WorkerSlot],
                      all_slots: list[WorkerSlot], watchdog: AdaptiveWatchdog,
                      *, now: float) -> list[tuple[str, WorkerSlot]] | None:
        """Plan next claims without mutating queue ownership or worker state.

        ``None`` requests the caller's conservative legacy placement policy.
        Every planned pair must still pass through ``dispatch`` and its queue
        adapter's atomic claim.
        """
        return adaptive_assignments(pending, active, completed, available,
                                    all_slots, watchdog, now)

    @staticmethod
    def _key(decision: Decision, snapshot_hash: str) -> str:
        body = {
            "policy": decision.policy_version,
            "task": decision.task_id,
            "worker": decision.worker_id,
            "snapshot": snapshot_hash,
        }
        return "fada-" + sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()

    def dispatch(
        self,
        tasks: list[Task],
        workers: list[WorkerSlot],
        estimator: ScenarioEstimator,
        queue: QueueBackend,
        *,
        now: float = 0.0,
        progress: Mapping[str, float] | None = None,
        scenario_status: Mapping[str, ScenarioStatus | ScenarioWorkStatus] | None = None,
    ) -> DispatchReceipt:
        if not tasks or not workers:
            decision = Decision("fallback", None, None, None, 0.0, "empty_queue_or_pool", self.policy.version)
        else:
            if isinstance(self.policy, (ConcurrentScenarioPolicy, CostBalancedScenarioPolicy)):
                decision = self.policy.choose(
                    tasks, workers, estimator, scenario_status=scenario_status, now=now
                )
            elif isinstance(self.policy, CostWeightedProgressPolicy):
                decision = self.policy.choose(
                    tasks, workers, estimator, progress=progress, now=now
                )
            else:
                decision = self.policy.choose(tasks, workers, estimator, now=now)
        snapshot = sha256(repr((tasks, workers)).encode()).hexdigest()
        key = self._key(decision, snapshot)
        if decision.action != "dispatch" or not decision.task_id or not decision.worker_id:
            return DispatchReceipt(decision, False, key, self.version)
        if not any(t.task_id == decision.task_id for t in tasks):
            raise RuntimeError("policy selected a task absent from queue snapshot")
        if not any(w.worker_id == decision.worker_id and w.enabled for w in workers):
            raise RuntimeError("policy selected a worker absent from enabled snapshot")
        claimed = bool(queue.claim(decision.task_id, decision.worker_id, key))
        return DispatchReceipt(decision, claimed, key, self.version)
