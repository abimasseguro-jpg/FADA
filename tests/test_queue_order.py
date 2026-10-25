import unittest

from fada.domain import Task
from fada.queue_order import interleave_scenarios


class QueueOrderTests(unittest.TestCase):
    def test_balances_scenario_prefixes_and_preserves_within_scenario_order(self):
        tasks = [Task(f"{scenario}{rep}", scenario)
                 for scenario in ("n100", "n200", "n400")
                 for rep in range(3)]

        ordered = interleave_scenarios(tasks)

        self.assertEqual([task.task_id for task in ordered],
                         [f"{scenario}{rep}" for rep in range(3)
                          for scenario in ("n100", "n200", "n400")])
        for prefix in range(1, len(ordered) + 1):
            counts = [sum(task.scenario == scenario for task in ordered[:prefix])
                      for scenario in ("n100", "n200", "n400")]
            self.assertLessEqual(max(counts) - min(counts), 1)
        self.assertEqual({task.task_id for task in ordered},
                         {task.task_id for task in tasks})
        self.assertEqual([task.task_id for task in tasks[:3]],
                         ["n1000", "n1001", "n1002"])

    def test_unequal_scenarios_keep_all_tasks_and_internal_order(self):
        tasks = [Task("a1", "a"), Task("a2", "a"), Task("a3", "a"),
                 Task("b1", "b"), Task("c1", "c"), Task("c2", "c")]
        self.assertEqual([task.task_id for task in interleave_scenarios(tasks)],
                         ["a1", "b1", "c1", "a2", "c2", "a3"])
        self.assertEqual(interleave_scenarios([]), [])

    def test_duplicate_identity_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "duplicate task_id"):
            interleave_scenarios([Task("same", "a"), Task("same", "b")])


if __name__ == "__main__":
    unittest.main()
