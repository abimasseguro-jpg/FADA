"""Pure, opt-in adaptive scheduling for the shared FADA worker pool.

The controller only ranks pending tasks. Ownership, recovery and publication
remain with the existing dispatcher and worker guard.
"""
from __future__ import annotations

import collections
import math
import re
from dataclasses import asdict, dataclass

BASE_COST = {1: 1.0, 2: 2.0, 3: 4.0}
RATE_COST = {i: (1.05, 1.15, 1.30)[(i - 1) % 3] for i in range(1, 10)}
TASK_RE = re.compile(r"^d(0[1-3])_i(0[1-9])_r\d{3}$")


def key(task_id: str) -> tuple[int, int]:
    match = TASK_RE.fullmatch(task_id)
    if not match:
        raise ValueError(f"Invalid FADA task ID: {task_id}")
    return int(match[1]), int(match[2])


@dataclass(frozen=True)
class AdaptiveConfig:
    interval_seconds: float = 60.0
    completion_block: int = 12
    sync_gap: float = 0.005
    recovery_gap: float = 0.01
    eta_gap: float = 0.05
    confirmations: int = 3
    cooldown_seconds: float = 180.0
    max_target_change: float = 0.12
    ewma_alpha: float = 0.25
    min_samples: int = 3
    final_pending_per_slot: float = 1.0

    def validate(self) -> None:
        if (self.interval_seconds <= 0 or self.completion_block < 1 or
                not 0 < self.sync_gap < self.recovery_gap < 1 or
                not 0 < self.eta_gap < 1 or self.confirmations < 1 or
                self.cooldown_seconds < 0 or not 0 < self.max_target_change <= 1 or
                not 0 < self.ewma_alpha <= 1 or self.min_samples < 1 or
                self.final_pending_per_slot <= 0):
            raise ValueError("Invalid adaptive scheduling parameters")


class AdaptiveWatchdog:
    def __init__(self, config: AdaptiveConfig, saved: dict | None = None):
        config.validate()
        self.config = config
        saved = saved or {}
        if saved.get("schema", "fada-adaptive-v1") != "fada-adaptive-v1":
            raise ValueError("Unknown adaptive watchdog state schema")
        self.phase = saved.get("phase", "DEGRADED")
        if self.phase not in {"RECOVERY", "SYNCHRONIZED", "REBALANCING",
                              "FINALIZATION", "DEGRADED"}:
            raise ValueError("Invalid adaptive watchdog phase")
        self.confirmed = int(saved.get("confirmed", 0))
        self.last_evaluation = float(saved.get("last_evaluation", 0))
        self.last_transition = float(saved.get("last_transition", 0))
        self.last_completed = int(saved.get("last_completed", -1))
        self.targets = {int(k): float(v) for k, v in saved.get("targets", {}).items()}
        if any(d not in BASE_COST or not math.isfinite(v) or v < 0
               for d, v in self.targets.items()):
            raise ValueError("Invalid saved adaptive capacity target")
        self.samples = {str(k): dict(v) for k, v in saved.get("samples", {}).items()}
        self.rate = {int(k): float(v) for k, v in saved.get("rate", {}).items()}
        self.rate_counts = {int(k): int(v) for k, v in saved.get("rate_counts", {}).items()}
        self.rate_at = float(saved.get("rate_at", 0))
        self.events = []
        self.report = saved.get("report", {})

    def save(self) -> dict:
        return dict(schema="fada-adaptive-v1", config=asdict(self.config),
                    phase=self.phase, confirmed=self.confirmed,
                    last_evaluation=self.last_evaluation,
                    last_transition=self.last_transition,
                    last_completed=self.last_completed,
                    targets=self.targets, samples=self.samples, rate=self.rate,
                    rate_counts=self.rate_counts, rate_at=self.rate_at,
                    report=self.report)

    def observe(self, task_id: str, elapsed_seconds: float, worker_speed: float) -> None:
        if not (math.isfinite(elapsed_seconds) and elapsed_seconds > 0 and
                math.isfinite(worker_speed) and worker_speed > 0):
            return
        name = "%d:%d" % key(task_id)
        normalized = elapsed_seconds * worker_speed
        old = self.samples.get(name)
        alpha = self.config.ewma_alpha
        value = normalized if old is None else alpha * normalized + (1 - alpha) * old["ewma"]
        self.samples[name] = {"ewma": value, "count": min(100000, 1 + int(old["count"])) if old else 1}

    def cost(self, stratum: tuple[int, int]) -> float:
        base = BASE_COST[stratum[0]] * RATE_COST[stratum[1]]
        sample = self.samples.get("%d:%d" % stratum)
        if not sample or sample["count"] < self.config.min_samples:
            return base
        # Calibrate in base-cost units so cold and warm strata remain comparable.
        ratios = [v["ewma"] / (BASE_COST[int(k.split(":")[0])] *
                    RATE_COST[int(k.split(":")[1])]) for k, v in self.samples.items()
                  if v["count"] >= self.config.min_samples]
        scale = sorted(ratios)[len(ratios) // 2]
        return base * max(0.25, min(4.0, sample["ewma"] / (base * scale)))

    def _snapshot(self, pending, active, completed, slots, now):
        all_ids = list(pending) + list(active) + list(completed)
        if len(set(all_ids)) != len(all_ids):
            raise ValueError("Pending, active and completed task ownership overlaps")
        counts = {d: {"pending": 0, "active": 0, "completed": 0, "total": 0,
                      "work": 0.0, "capacity": 0.0, "workers": 0} for d in BASE_COST}
        pending_costs = {d: [] for d in BASE_COST}
        active_costs = {d: [] for d in BASE_COST}
        speed_by_worker = {slot.worker_id: slot.speed for slot in slots}
        active_workers = [str(item.get("worker_id", "")) for item in active.values()]
        if len(set(active_workers)) != len(active_workers):
            raise ValueError("Multiple active tasks assigned to one worker")
        if any(not math.isfinite(v) or v <= 0 for v in speed_by_worker.values()):
            raise ValueError("Invalid worker speed")
        for task_id in completed:
            counts[key(task_id)[0]]["completed"] += 1
        for task_id in pending:
            d = key(task_id)[0]
            counts[d]["pending"] += 1
            pending_costs[d].append(self.cost(key(task_id)))
        for task_id, item in active.items():
            d = key(task_id)[0]
            worker_id = str(item.get("worker_id", ""))
            speed = speed_by_worker.get(worker_id)
            if speed is None:
                raise ValueError("Active worker missing from configured pool")
            elapsed = max(0.0, now - float(item.get("launched_at", now)))
            cost = self.cost(key(task_id))
            # Elapsed work is discounted, with a floor for long-tail uncertainty.
            unit_seconds = self._unit_seconds()
            residual = max(0.25 * cost, cost - elapsed * speed / unit_seconds)
            active_costs[d].append(residual)
            counts[d]["active"] += 1
            counts[d]["capacity"] += speed
            counts[d]["workers"] += 1
        for d, row in counts.items():
            row["total"] = row["pending"] + row["active"] + row["completed"]
            row["progress"] = row["completed"] / row["total"] if row["total"] else 1.0
            row["work"] = sum(pending_costs[d]) + sum(active_costs[d])
        return counts, pending_costs, active_costs

    def _unit_seconds(self):
        ratios = [v["ewma"] / (BASE_COST[int(k.split(":")[0])] *
                    RATE_COST[int(k.split(":")[1])]) for k, v in self.samples.items()
                  if v["count"] >= self.config.min_samples]
        return max(1.0, sorted(ratios)[len(ratios) // 2]) if ratios else 60.0

    def evaluate(self, pending, active, completed, slots, now, force=False):
        count = len(completed)
        if (not force and now - self.last_evaluation < self.config.interval_seconds and
                count - self.last_completed < self.config.completion_block):
            return self.report
        self.last_evaluation, self.last_completed = now, count
        try:
            rows, pending_costs, active_costs = self._snapshot(pending, active, completed, slots, now)
            if not slots or not any(row["pending"] or row["active"] for row in rows.values()):
                raise ValueError("No eligible pool or work")
            progress = [row["progress"] for row in rows.values() if row["total"]]
            gap = max(progress) - min(progress) if progress else 0.0
            total_capacity = sum(slot.speed for slot in slots)
            remaining = sum(row["pending"] + row["active"] for row in rows.values())
            final = remaining <= len(slots) * self.config.final_pending_per_slot
            completed_by_d = {d: rows[d]["completed"] for d in BASE_COST}
            if self.rate_at == 0:
                self.rate_at, self.rate_counts = now, completed_by_d
            elif (now - self.rate_at >= self.config.interval_seconds or
                  count - sum(self.rate_counts.values()) >= self.config.completion_block):
                dt = max(1.0, now - self.rate_at)
                for d in BASE_COST:
                    observed = max(0, completed_by_d[d] - self.rate_counts.get(d, 0)) * 3600 / dt
                    self.rate[d] = (observed if d not in self.rate else
                                    self.config.ewma_alpha * observed +
                                    (1 - self.config.ewma_alpha) * self.rate[d])
                self.rate_at, self.rate_counts = now, completed_by_d
            # Recovery horizon is just beyond the leader, bounded by completion.
            horizon = min(1.0, max(progress) + max(0.02, self.config.sync_gap))
            horizon_work = {}
            for d, row in rows.items():
                needed = max(0, math.ceil(horizon * row["total"]) - row["completed"] - row["active"])
                horizon_work[d] = sum(active_costs[d]) + sum(sorted(pending_costs[d])[:needed])
            work = {d: (rows[d]["work"] if self.phase != "RECOVERY" or final else horizon_work[d])
                    for d in BASE_COST}
            eta = {d: (rows[d]["work"] / max(rows[d]["capacity"], 1e-9) * self._unit_seconds())
                   for d in BASE_COST if rows[d]["work"] > 0 and rows[d]["capacity"] > 0}
            eta_spread = ((max(eta.values()) - min(eta.values())) / max(eta.values())
                          if len(eta) == 3 and max(eta.values()) > self._unit_seconds() else None)
            enough_eta = eta_spread is not None and sum(v["count"] >= self.config.min_samples
                                                       for v in self.samples.values()) >= 3
            synchronized = gap <= self.config.sync_gap and enough_eta and eta_spread <= self.config.eta_gap
            if synchronized:
                self.confirmed += 1
            else:
                self.confirmed = 0
            previous = self.phase
            if final:
                desired = "FINALIZATION"
            elif gap >= self.config.recovery_gap:
                desired = "RECOVERY"
            elif self.phase == "RECOVERY" and self.confirmed < self.config.confirmations:
                desired = "RECOVERY"
            elif synchronized and self.confirmed >= self.config.confirmations:
                desired = "SYNCHRONIZED"
            else:
                desired = "REBALANCING"
            if desired != self.phase and (self.phase == "DEGRADED" or desired == "FINALIZATION" or
                                          now - self.last_transition >= self.config.cooldown_seconds):
                self.phase, self.last_transition = desired, now
                if previous == "SYNCHRONIZED" and desired in ("RECOVERY", "REBALANCING"):
                    self.events.append({"event": "DRIFT_DETECTED", "at": now, "gap": gap})
                event = {"RECOVERY": "RECOVERY_STARTED", "SYNCHRONIZED": "SYNCHRONIZATION_ACHIEVED",
                         "REBALANCING": "REBALANCING_STARTED", "FINALIZATION": "FINALIZATION_STARTED"}[desired]
                self.events.append({"event": event, "at": now, "from": previous, "to": desired})
            work = {d: (horizon_work[d] if self.phase == "RECOVERY" and not final else rows[d]["work"])
                    for d in BASE_COST}
            work_sum = sum(work.values())
            raw = {d: total_capacity * work[d] / work_sum if work_sum else 0.0 for d in BASE_COST}
            # Slew limit applies only after a previous target exists. Redistribute
            # the resulting fractions to retain full capacity.
            if self.targets and self.phase != "DEGRADED":
                limit = total_capacity * self.config.max_target_change
                raw = {d: (max(self.targets.get(d, 0.0) - limit,
                               min(self.targets.get(d, 0.0) + limit, raw[d])) if work[d] > 0 else 0.0)
                       for d in BASE_COST}
                scale = total_capacity / sum(raw.values()) if sum(raw.values()) else 1.0
                raw = {d: value * scale for d, value in raw.items()}
            if self.targets and any(abs(raw[d] - self.targets.get(d, 0)) > total_capacity * 0.05
                                    for d in BASE_COST):
                self.events.append({"event": "CAPACITY_REBALANCED", "at": now,
                                    "targets": raw})
            self.targets = raw
            stage = ("final" if final else "initial" if len(self.samples) < 3 else
                     "advanced" if max(progress) >= 0.8 or remaining <= 5 * len(slots) else
                     "intermediate")
            self.report = {"phase": self.phase, "progress_gap": gap, "horizon": horizon,
                           "eta_spread": eta_spread, "eta_seconds": eta,
                           "stage": stage, "throughput_per_hour": self.rate,
                           "campaigns": {d: {**row, "target": raw[d],
                                              "deficit": raw[d] - row["capacity"]}
                                         for d, row in rows.items()},
                           "at": now, "samples": len(self.samples)}
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            if self.phase != "DEGRADED":
                self.events.append({"event": "WATCHDOG_DEGRADED", "at": now, "error": str(exc)})
            self.phase = "DEGRADED"
            self.report = {"phase": "DEGRADED", "error": str(exc), "at": now}
        return self.report


def adaptive_assignments(pending, active, completed, available, all_slots, watchdog, now):
    """Assign every eligible free slot; never claim or mutate task state here."""
    report = watchdog.evaluate(pending, active, completed, all_slots, now)
    if report.get("phase") == "DEGRADED":
        return None
    buckets = collections.defaultdict(collections.deque)
    load = collections.Counter(key(task_id) for task_id in completed)
    load.update(key(task_id) for task_id in active)
    for task_id in pending:
        buckets[key(task_id)].append(task_id)
    speed_by_worker = {slot.worker_id: slot.speed for slot in all_slots}
    occupied = {d: 0.0 for d in BASE_COST}
    for task_id, item in active.items():
        occupied[key(task_id)[0]] += speed_by_worker[item["worker_id"]]
    assignments = []
    speeds = sorted(slot.speed for slot in available)
    median_speed = speeds[len(speeds) // 2] if speeds else 0.0
    for slot in sorted(available, key=lambda item: (-item.speed, item.worker_id)):
        candidates = {item[0] for item, values in buckets.items() if values}
        if not candidates:
            break
        # Deficit is recomputed after each simulated assignment. A nonpositive
        # deficit never idles a worker when eligible work remains.
        d = max(candidates, key=lambda d: (watchdog.targets[d] - occupied[d],
                                           report["campaigns"][d]["work"], -d))
        strata = [item for item in buckets if item[0] == d and buckets[item]]
        minimum = min(load[item] for item in strata)
        lagging = [item for item in strata if load[item] == minimum]
        selected = (max(lagging, key=lambda item: (watchdog.cost(item), -item[1]))
                    if slot.speed >= median_speed else
                    min(lagging, key=lambda item: (watchdog.cost(item), item[1])))
        assignments.append((buckets[selected].popleft(), slot))
        load[selected] += 1
        occupied[d] += slot.speed
    return assignments
