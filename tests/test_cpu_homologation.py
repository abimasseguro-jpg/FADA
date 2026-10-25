from __future__ import annotations

import unittest

from fada.cpu_homologation import (
    CPU_HOMOLOGATION_KERNEL_VERSION,
    discover_cpu_capability,
    run_cpu_kernel,
)


class CpuHomologationTests(unittest.TestCase):
    def test_capability_is_explicitly_cpu_and_affinity_is_nonempty(self) -> None:
        capability = discover_cpu_capability()
        self.assertEqual(capability.resource_kind, "cpu")
        self.assertTrue(capability.architecture)
        self.assertGreaterEqual(capability.logical_cpus, 1)
        self.assertTrue(capability.affinity_cpus)
        self.assertTrue(
            set(capability.affinity_cpus).issubset(range(capability.logical_cpus))
        )

    def test_kernel_is_deterministic_and_worker_specific(self) -> None:
        first = run_cpu_kernel(0, 20, "seed")
        repeated = run_cpu_kernel(0, 20, "seed")
        other_worker = run_cpu_kernel(1, 20, "seed")
        self.assertEqual(first, repeated)
        self.assertNotEqual(first.digest, other_worker.digest)
        self.assertEqual(len(first.digest), 64)
        self.assertEqual(CPU_HOMOLOGATION_KERNEL_VERSION, "fada-cpu-kernel/1")

    def test_kernel_rejects_ambiguous_or_invalid_inputs(self) -> None:
        for worker, iterations, seed in (
            (-1, 1, "seed"),
            (True, 1, "seed"),
            (0, 0, "seed"),
            (0, True, "seed"),
            (0, 1, ""),
        ):
            with self.subTest(worker=worker, iterations=iterations, seed=seed):
                with self.assertRaises(ValueError):
                    run_cpu_kernel(worker, iterations, seed)


if __name__ == "__main__":
    unittest.main()
