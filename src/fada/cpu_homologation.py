"""Observational CPU capability discovery and deterministic qualification kernel."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import os
import platform
import sys


CPU_HOMOLOGATION_KERNEL_VERSION = "fada-cpu-kernel/1"


@dataclass(frozen=True, slots=True)
class CpuCapability:
    """CPU execution identity; discovery never changes host configuration."""

    resource_kind: str
    architecture: str
    logical_cpus: int
    affinity_cpus: tuple[int, ...]
    byte_order: str
    python_implementation: str
    python_version: str
    kernel_release: str

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["affinity_cpus"] = list(self.affinity_cpus)
        return result


@dataclass(frozen=True, slots=True)
class CpuKernelResult:
    worker_index: int
    iterations: int
    digest: str


def discover_cpu_capability() -> CpuCapability:
    """Return only locally observable CPU/runtime properties."""

    logical_cpus = os.cpu_count() or 1
    if hasattr(os, "sched_getaffinity"):
        affinity = tuple(sorted(os.sched_getaffinity(0)))
    else:  # pragma: no cover - portability fallback
        affinity = tuple(range(logical_cpus))
    if not affinity:
        raise RuntimeError("CPU affinity is empty")
    return CpuCapability(
        resource_kind="cpu",
        architecture=platform.machine() or "unknown",
        logical_cpus=logical_cpus,
        affinity_cpus=affinity,
        byte_order=sys.byteorder,
        python_implementation=platform.python_implementation(),
        python_version=platform.python_version(),
        kernel_release=platform.release(),
    )


def run_cpu_kernel(worker_index: int, iterations: int, seed: str) -> CpuKernelResult:
    """Run a deterministic CPU-bound kernel with no external side effects."""

    if isinstance(worker_index, bool) or not isinstance(worker_index, int):
        raise ValueError("worker_index must be an integer")
    if worker_index < 0:
        raise ValueError("worker_index must be non-negative")
    if isinstance(iterations, bool) or not isinstance(iterations, int):
        raise ValueError("iterations must be an integer")
    if iterations < 1:
        raise ValueError("iterations must be positive")
    if not isinstance(seed, str) or not seed:
        raise ValueError("seed must be a non-empty string")

    state = sha256(
        f"{CPU_HOMOLOGATION_KERNEL_VERSION}:{seed}:{worker_index}".encode("utf-8")
    ).digest()
    for index in range(iterations):
        state = sha256(state + index.to_bytes(8, "little", signed=False)).digest()
    return CpuKernelResult(
        worker_index=worker_index,
        iterations=iterations,
        digest=state.hex(),
    )
