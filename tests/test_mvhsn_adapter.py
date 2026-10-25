from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class MvhsnShadowAdapterTests(unittest.TestCase):
    def test_shadow_report_does_not_mutate_or_assign_queue_rows(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "queue.sqlite"
            output = Path(directory) / "shadow.json"
            connection = sqlite3.connect(database)
            connection.execute(
                """create table tasks (
                    id integer primary key,
                    status text not null,
                    payload_json text not null,
                    completed_by text,
                    task_elapsed_seconds real,
                    leased_by text
                )"""
            )
            rows = [
                (1, "complete", '{"n": 100}', "local", 10.0, None),
                (2, "pending", '{"n": 100}', None, None, None),
                (3, "leased", '{"n": 200}', None, None, "wsl"),
            ]
            connection.executemany("insert into tasks values (?, ?, ?, ?, ?, ?)", rows)
            connection.commit()
            before = connection.execute("select * from tasks order by id").fetchall()
            connection.close()

            process = subprocess.run(
                [
                    sys.executable,
                    "adapters/mvhsn/fada_shadow_report.py",
                    "--database",
                    str(database),
                    "--output",
                    str(output),
                ],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(report["read_only"])
            self.assertEqual(report["database_open_mode"], "mode=ro")
            self.assertFalse(report["eligibility_verified"])
            self.assertEqual(report["recommendations"], [])

            connection = sqlite3.connect(database)
            after = connection.execute("select * from tasks order by id").fetchall()
            connection.close()
            self.assertEqual(after, before)
            self.assertEqual(after[1][1], "pending")

    def test_gpu_campaign_uses_explicit_worker_capabilities(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "queue.sqlite"
            workers = Path(directory) / "gpu_workers.csv"
            output = Path(directory) / "shadow.json"
            connection = sqlite3.connect(database)
            connection.execute(
                """create table tasks (
                    id integer primary key, status text not null,
                    payload_json text not null, completed_by text,
                    task_elapsed_seconds real, leased_by text
                )"""
            )
            payload = json.dumps(
                {"n": 100, "execution_class": "gpu", "requires_gpu": "true"}
            )
            connection.executemany(
                "insert into tasks values (?, ?, ?, ?, ?, ?)",
                [
                    (1, "complete", payload, "gpu-a", 10.0, None),
                    (2, "pending", payload, None, None, None),
                ],
            )
            connection.commit()
            connection.close()
            workers.write_text(
                "machine,task_slots,gpu_backend,enabled\n"
                "gpu-a,2,cuda,true\n",
                encoding="utf-8",
            )
            process = subprocess.run(
                [
                    sys.executable,
                    "adapters/mvhsn/fada_shadow_report.py",
                    "--database", str(database),
                    "--gpu-workers-csv", str(workers),
                    "--output", str(output),
                ],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(report["eligibility_verified"])
            self.assertEqual(report["worker_capacities"], {"gpu-a": 2})
            self.assertEqual(report["worker_backends"], {"gpu-a": "cuda"})
            self.assertEqual(report["recommendations"][0]["machine"], "gpu-a")


if __name__ == "__main__":
    unittest.main()
