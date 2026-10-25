#!/usr/bin/env python3
"""Paired temporal backtest for FADA-HS and deterministic baselines."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import math
import random
import statistics
import sys
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fada import (
    BoundedPlanGuardedHybridPolicy, DurationObservation, ExecutionOutcome,
    GuardedHybridPolicy, HybridPolicy, PlanGuardedHybridPolicy,
    PolicyEstimatorAdapter, ScenarioEstimator, StratifiedDurationEstimator, Task, WorkerSlot,
)


SCENARIO_SECONDS = {"xs": 5.0, "small": 15.0, "medium": 45.0, "large": 120.0}
WORKER_SPECS = (
    ("fast-0", "fast", 1.40),
    ("fast-1", "fast", 1.40),
    ("medium-0", "medium", 1.00),
    ("slow-0", "slow", 0.65),
)
POLICIES = (
    "fifo", "interleaved", "min_min", "max_min", "sufferage", "fada", "fada_v02", "fada_v03", "fada_v04", "fada_v04_est02",
)


@dataclass(frozen=True, slots=True)
class Trace:
    tasks: tuple[Task, ...]
    workers: tuple[WorkerSlot, ...]
    estimator: ScenarioEstimator
    actual: dict[tuple[str, str], float]


@dataclass(frozen=True, slots=True)
class RunMetrics:
    makespan: float
    idle_fraction: float
    eta_relative_error: float
    decision_mean_ms: float
    decision_p95_ms: float


def percentile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    ordered = sorted(values)
    position = min(len(ordered) - 1, max(0, math.ceil(probability * len(ordered)) - 1))
    return ordered[position]


def lognormal_multiplier(rng: random.Random, cv: float) -> float:
    sigma = math.sqrt(math.log1p(cv * cv))
    return rng.lognormvariate(-0.5 * sigma * sigma, sigma)


def build_trace(
    seed: int,
    *,
    tasks_per_scenario: int,
    training_samples: int = 8,
    cv: float = 0.25,
    failure_rate: float = 0.02,
) -> Trace:
    """Build temporally separated training observations and evaluation tasks."""
    rng = random.Random(seed)
    estimator = ScenarioEstimator(minimum_samples=training_samples)
    workers = tuple(WorkerSlot(*spec) for spec in WORKER_SPECS)

    # Training phase: only observations before the evaluation cutoff are exposed.
    for scenario, base in SCENARIO_SECONDS.items():
        for machine, speed in (("fast", 1.40), ("medium", 1.00), ("slow", 0.65)):
            for _ in range(training_samples):
                elapsed = base / speed * lognormal_multiplier(rng, cv)
                estimator.observe(scenario, machine, elapsed)

    tasks = [
        Task(
            task_id=f"{scenario}-{index:03d}",
            scenario=scenario,
            complexity=rng.uniform(0.85, 1.15),
        )
        for scenario in SCENARIO_SECONDS
        for index in range(tasks_per_scenario)
    ]
    rng.shuffle(tasks)

    # Evaluation phase: moderate temporal drift and rare multiplicative failures.
    actual: dict[tuple[str, str], float] = {}
    for task in sorted(tasks, key=lambda item: item.task_id):
        scenario_index = tuple(SCENARIO_SECONDS).index(task.scenario)
        scenario_drift = 1.0 + (scenario_index - 1.5) * 0.04
        for worker in workers:
            machine_drift = {"fast": 1.06, "medium": 0.98, "slow": 1.03}[worker.machine]
            elapsed = (
                SCENARIO_SECONDS[task.scenario]
                * task.complexity
                / worker.speed
                * scenario_drift
                * machine_drift
                * lognormal_multiplier(rng, cv)
            )
            if rng.random() < failure_rate:
                elapsed *= 2.5
            actual[(task.task_id, worker.worker_id)] = elapsed
    return Trace(tuple(tasks), workers, estimator, actual)


def predicted_duration(trace: Trace, task: Task, worker: WorkerSlot) -> float:
    estimate = trace.estimator.estimate(task, worker)
    if estimate is None:
        raise RuntimeError("backtest trace unexpectedly lacks estimate coverage")
    return estimate[0]


def estimator_v02_adapter(trace: Trace) -> PolicyEstimatorAdapter:
    """Convert only pre-cutoff 0.1 training samples to the isolated EST 0.2 contract."""
    estimator = StratifiedDurationEstimator(minimum_samples=3)
    sequence = 0
    for (scenario, machine), values in sorted(trace.estimator._samples.items()):
        for elapsed in values:
            estimator.observe(DurationObservation(
                observation_id=f"temporal-training:{scenario}:{machine}:{sequence}",
                scenario=scenario, machine_id=machine, backend="cpu",
                hardware_profile="synthetic-v1", active_workers=1,
                observed_at=0.0, outcome=ExecutionOutcome.COMPLETED,
                elapsed_seconds=elapsed,
            ))
            sequence += 1
    return PolicyEstimatorAdapter(estimator, "cpu", "synthetic-v1", now=10_000.0)


def interleaved_order(tasks: list[Task]) -> list[Task]:
    groups: dict[str, deque[Task]] = {
        scenario: deque(task for task in tasks if task.scenario == scenario)
        for scenario in SCENARIO_SECONDS
    }
    result: list[Task] = []
    while any(groups.values()):
        for scenario in SCENARIO_SECONDS:
            if groups[scenario]:
                result.append(groups[scenario].popleft())
    return result


def schedule(trace: Trace, policy_name: str) -> RunMetrics:
    if policy_name not in POLICIES:
        raise ValueError(f"unknown policy: {policy_name}")
    remaining = list(trace.tasks)
    if policy_name == "interleaved":
        remaining = interleaved_order(remaining)
    predicted_load = {worker.worker_id: 0.0 for worker in trace.workers}
    actual_load = {worker.worker_id: 0.0 for worker in trace.workers}
    errors: list[float] = []
    decision_times: list[float] = []
    decision_estimator = estimator_v02_adapter(trace) if policy_name == "fada_v04_est02" else trace.estimator
    fada = HybridPolicy(
        candidate_window=8,
        projection_limit=24,
        uncertainty_weight=0.5,
    )

    def completions(task: Task) -> list[tuple[float, str, WorkerSlot]]:
        return sorted(
            (
                predicted_load[worker.worker_id]
                + (decision_estimator.estimate(task, worker) or (_missing_estimate()))[0],
                worker.worker_id,
                worker,
            )
            for worker in trace.workers
        )

    while remaining:
        started = time.perf_counter_ns()
        if policy_name in {"fifo", "interleaved"}:
            task = remaining[0]
            worker = completions(task)[0][2]
        elif policy_name in {"min_min", "max_min"}:
            options = [(completions(task)[0], task.task_id, task) for task in remaining]
            selected = min(options) if policy_name == "min_min" else max(options)
            task = selected[2]
            worker = selected[0][2]
        elif policy_name == "sufferage":
            options = []
            for task_option in remaining:
                ranked = completions(task_option)
                gap = ranked[1][0] - ranked[0][0]
                options.append((-gap, ranked[0][0], task_option.task_id, task_option, ranked[0][2]))
            _, _, _, task, worker = min(options)
        elif policy_name == "fada":
            decision_workers = [
                WorkerSlot(
                    worker.worker_id,
                    worker.machine,
                    worker.speed,
                    available_at=predicted_load[worker.worker_id],
                )
                for worker in trace.workers
            ]
            decision = fada.choose(remaining, decision_workers, trace.estimator)
            if decision.action != "dispatch":
                raise RuntimeError(f"FADA backtest decision was {decision.action}: {decision.reason}")
            task = next(item for item in remaining if item.task_id == decision.task_id)
            worker = next(item for item in trace.workers if item.worker_id == decision.worker_id)
        elif policy_name == "fada_v02":
            decision_workers = [
                WorkerSlot(worker.worker_id, worker.machine, worker.speed, available_at=predicted_load[worker.worker_id])
                for worker in trace.workers
            ]
            decision = GuardedHybridPolicy().choose(remaining, decision_workers, trace.estimator)
            if decision.action != "dispatch":
                raise RuntimeError(f"FADA 0.2 backtest decision was {decision.action}: {decision.reason}")
            task = next(item for item in remaining if item.task_id == decision.task_id)
            worker = next(item for item in trace.workers if item.worker_id == decision.worker_id)
        elif policy_name == "fada_v03":
            decision_workers = [
                WorkerSlot(worker.worker_id, worker.machine, worker.speed, available_at=predicted_load[worker.worker_id])
                for worker in trace.workers
            ]
            decision = PlanGuardedHybridPolicy().choose(remaining, decision_workers, trace.estimator)
            if decision.action != "dispatch":
                raise RuntimeError(f"FADA 0.3 backtest decision was {decision.action}: {decision.reason}")
            task = next(item for item in remaining if item.task_id == decision.task_id)
            worker = next(item for item in trace.workers if item.worker_id == decision.worker_id)
        else:
            decision_workers = [
                WorkerSlot(worker.worker_id, worker.machine, worker.speed, available_at=predicted_load[worker.worker_id])
                for worker in trace.workers
            ]
            decision = BoundedPlanGuardedHybridPolicy().choose(remaining, decision_workers, decision_estimator)
            if decision.action != "dispatch":
                raise RuntimeError(f"FADA 0.4 backtest decision was {decision.action}: {decision.reason}")
            task = next(item for item in remaining if item.task_id == decision.task_id)
            worker = next(item for item in trace.workers if item.worker_id == decision.worker_id)
        decision_times.append((time.perf_counter_ns() - started) / 1_000_000)

        value = decision_estimator.estimate(task, worker)
        if value is None:
            raise RuntimeError("backtest trace unexpectedly lacks estimate coverage")
        estimate = value[0]
        elapsed = trace.actual[(task.task_id, worker.worker_id)]
        predicted_load[worker.worker_id] += estimate
        actual_load[worker.worker_id] += elapsed
        errors.append(abs(estimate - elapsed) / elapsed)
        remaining.remove(task)

    makespan = max(actual_load.values())
    total_work = sum(actual_load.values())
    idle_fraction = 1.0 - total_work / (makespan * len(trace.workers))
    return RunMetrics(
        makespan=makespan,
        idle_fraction=idle_fraction,
        eta_relative_error=statistics.mean(errors),
        decision_mean_ms=statistics.mean(decision_times),
        decision_p95_ms=percentile(decision_times, 0.95),
    )


def bootstrap_upper_relative_difference(
    candidate: list[float],
    baseline: list[float],
    *,
    samples: int,
    seed: int = 918273,
) -> float:
    if len(candidate) != len(baseline) or not candidate:
        raise ValueError("paired bootstrap requires equally sized nonempty samples")
    rng = random.Random(seed)
    differences = [(left - right) / right for left, right in zip(candidate, baseline)]
    bootstrapped = [
        statistics.mean(differences[rng.randrange(len(differences))] for _ in differences)
        for _ in range(samples)
    ]
    return percentile(bootstrapped, 0.95)


def aggregate(runs: list[RunMetrics]) -> dict[str, float]:
    return {
        "makespan_mean": statistics.mean(run.makespan for run in runs),
        "makespan_median": statistics.median(run.makespan for run in runs),
        "makespan_p95": percentile([run.makespan for run in runs], 0.95),
        "idle_fraction_mean": statistics.mean(run.idle_fraction for run in runs),
        "eta_relative_error_mean": statistics.mean(run.eta_relative_error for run in runs),
        "decision_mean_ms": statistics.mean(run.decision_mean_ms for run in runs),
        "decision_p95_ms": percentile([run.decision_p95_ms for run in runs], 0.95),
    }


def run_replicate(arguments: tuple[int, int]) -> dict[str, RunMetrics]:
    """Run one seed; module scope keeps it safe for process-based execution."""
    seed, tasks_per_scenario = arguments
    trace = build_trace(seed, tasks_per_scenario=tasks_per_scenario)
    return {policy_name: schedule(trace, policy_name) for policy_name in POLICIES}


def _missing_estimate() -> tuple[float, float]:
    raise RuntimeError("backtest trace unexpectedly lacks estimate coverage")


def run_backtest(
    *,
    replicates: int,
    tasks_per_scenario: int,
    bootstrap_samples: int,
    max_workers: int = 1,
    seed_start: int = 0,
    candidate_policy: str = "fada_v04",
) -> dict[str, object]:
    if replicates < 2 or tasks_per_scenario < 1 or bootstrap_samples < 10:
        raise ValueError("backtest requires >=2 replicates, tasks, and >=10 bootstrap samples")
    if max_workers < 1:
        raise ValueError("max_workers must be positive")
    if seed_start < 0:
        raise ValueError("seed_start cannot be negative")
    if candidate_policy not in POLICIES:
        raise ValueError("candidate policy must be registered")
    inputs = [(seed, tasks_per_scenario) for seed in range(seed_start, seed_start + replicates)]
    if max_workers == 1:
        replicated = [run_replicate(item) for item in inputs]
    else:
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            replicated = list(pool.map(run_replicate, inputs))
    runs: dict[str, list[RunMetrics]] = defaultdict(list)
    for replicate in replicated:
        for policy_name, metrics in replicate.items():
            runs[policy_name].append(metrics)

    summaries = {name: aggregate(runs[name]) for name in POLICIES}
    fada_makespan = [run.makespan for run in runs[candidate_policy]]
    sufferage_makespan = [run.makespan for run in runs["sufferage"]]
    upper = bootstrap_upper_relative_difference(
        fada_makespan,
        sufferage_makespan,
        samples=bootstrap_samples,
    )
    fada_summary = summaries[candidate_policy]
    comparator = summaries["sufferage"]
    criteria = {
        "paired_mean_regression_upper_95_le_0.02": upper <= 0.02,
        "makespan_p95_ratio_le_1.05": (
            fada_summary["makespan_p95"] / comparator["makespan_p95"] <= 1.05
        ),
        "idle_fraction_delta_le_0.02": (
            fada_summary["idle_fraction_mean"] - comparator["idle_fraction_mean"] <= 0.02
        ),
        "eta_error_delta_le_0.05": (
            fada_summary["eta_relative_error_mean"]
            - comparator["eta_relative_error_mean"]
            <= 0.05
        ),
        "decision_p95_ms_le_100": fada_summary["decision_p95_ms"] <= 100.0,
    }
    return {
        "schema_version": 1,
        "model": "FADA temporal paired backtest",
        "policy_version": "fada-hs/0.4-estimator-0.2" if candidate_policy == "fada_v04_est02" else "fada-hs/0.4",
        "candidate_policy": candidate_policy,
        "replicates": replicates,
        "seed_start": seed_start,
        "tasks_per_replicate": tasks_per_scenario * len(SCENARIO_SECONDS),
        "temporal_split": "training observations precede evaluation tasks",
        "primary_comparator": "sufferage",
        "max_workers": max_workers,
        "policies": summaries,
        "noninferiority": {
            "paired_mean_regression_upper_95": upper,
            "makespan_p95_ratio": (
                fada_summary["makespan_p95"] / comparator["makespan_p95"]
            ),
            "idle_fraction_delta": (
                fada_summary["idle_fraction_mean"] - comparator["idle_fraction_mean"]
            ),
            "eta_error_delta": (
                fada_summary["eta_relative_error_mean"]
                - comparator["eta_relative_error_mean"]
            ),
            "criteria": criteria,
            "passed": all(criteria.values()),
        },
        "read_only": True,
        "protocol": "governanca/gates/G2_PROTOCOL_2026-08-08.md",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replicates", type=int, default=200)
    parser.add_argument("--tasks-per-scenario", type=int, default=12)
    parser.add_argument("--bootstrap-samples", type=int, default=10_000)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--candidate-policy", choices=POLICIES, default="fada_v04")
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    report = run_backtest(
        replicates=arguments.replicates,
        tasks_per_scenario=arguments.tasks_per_scenario,
        bootstrap_samples=arguments.bootstrap_samples,
        max_workers=arguments.max_workers,
        seed_start=arguments.seed_start,
        candidate_policy=arguments.candidate_policy,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    arguments.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
