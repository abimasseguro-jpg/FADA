# FADA Adaptive Scheduling Watchdog

`src/fada/adaptive.py` provides an opt-in, pure placement controller for the
MVSNC `d01`–`d03` task grid. `FADADispatcher.plan_adaptive` returns candidate
task/worker pairs; the queue adapter still owns atomic claims. The existing
dispatcher default remains unchanged.

The controller starts from cost bases 1:2:4 and incompleteness multipliers
1.05/1.15/1.30. Verified final task durations update a bounded EWMA by stratum;
until three samples exist, the base costs remain the fallback. Active tasks
contribute an elapsed-time discounted residual with a 25% floor. Capacity is
the sum of configured worker speeds. `RECOVERY` uses a moving horizon just past
the leading campaign; `SYNCHRONIZED` and `REBALANCING` use remaining work;
`FINALIZATION` handles tails. Invalid or inconsistent ownership enters
`DEGRADED`, causing the caller to use its legacy planner. Phase changes use
three confirmations, cooldown and target slew limits.

The watchdog never claims, cancels, restarts, or marks a scientific task. It
does not infer a dead worker from duration alone. Callers must supply a
reconciled queue snapshot and pass each pair through the existing atomic claim.
Infrastructure loss that safely returns a task to the pending queue is modeled
as `ExecutionOutcome.REQUEUED`; it is recorded for recovery accounting and is
not counted as a scientific failure or a duration sample. A task is marked
`FAILED` only when the execution outcome itself is a failure after the caller's
reconciliation policy.
The current task ID parser and cost table are specific to the MVSNC p3q3 grid;
another campaign needs an explicit adapter and validation.

Validation: `PYTHONPATH=src python3 -m unittest tests.test_adaptive tests.test_dispatcher`.
The MVSNC integration, historical replay and live shadow are documented in
`/home/atilapcorreia/ARTIGOS/MVSNC/campaign/domestic_p3q3/ADAPTIVE_SCHEDULING.md`.
