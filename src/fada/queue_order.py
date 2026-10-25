"""Pure, opt-in ordering of a campaign's pending tasks by scenario."""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence

from .domain import Task


def interleave_scenarios(tasks: Sequence[Task]) -> list[Task]:
    """Round-robin scenarios while preserving each scenario's original order.

    The first appearance of a scenario determines its place in the cycle.
    Exhausted scenarios leave the cycle; no task is assigned to a worker here.
    This must be applied only when a host project creates a new pending queue,
    never to an active queue with persisted ownership or retry priority.
    """
    groups: dict[str, deque[Task]] = {}
    seen: set[str] = set()
    for task in tasks:
        if task.task_id in seen:
            raise ValueError(f"duplicate task_id: {task.task_id}")
        seen.add(task.task_id)
        groups.setdefault(task.scenario, deque()).append(task)

    ordered: list[Task] = []
    cycle = deque(groups)
    while cycle:
        scenario = cycle.popleft()
        group = groups[scenario]
        ordered.append(group.popleft())
        if group:
            cycle.append(scenario)
    return ordered
