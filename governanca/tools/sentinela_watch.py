#!/usr/bin/env python3
"""Portable, observational file watcher for project governance."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path


IGNORED_DIRS = {
    ".git", ".pytest_cache", ".runtime", "__pycache__", "build", "dist",
    "output", "outputs", "Release", "results", "work", "evidencias",
}
IGNORED_SUFFIXES = {".log", ".out", ".pid", ".pyc", ".tmp", ".tar.gz"}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def append_log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(message.rstrip() + "\n")


def load_config(root: Path) -> dict[str, object]:
    path = root / "governanca/sentinela_project.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not str(payload.get("project_id", "")).strip():
        raise ValueError("sentinela_project.json requires project_id")
    return payload


def ignored(relative: Path) -> bool:
    return bool(set(relative.parts) & IGNORED_DIRS) or any(
        relative.name.endswith(suffix) for suffix in IGNORED_SUFFIXES
    )


def snapshot(root: Path) -> dict[str, tuple[int, int]]:
    state: dict[str, tuple[int, int]] = {}
    for directory, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = [name for name in dirnames if name not in IGNORED_DIRS]
        base = Path(directory)
        for filename in filenames:
            path = base / filename
            relative = path.relative_to(root)
            if ignored(relative):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            state[str(relative)] = (stat.st_mtime_ns, stat.st_size)
    return state


def run(command: list[str], root: Path, log: Path, label: str) -> int:
    append_log(log, f"[SENTINELA] {label}_command={' '.join(command)}")
    try:
        result = subprocess.run(
            command, cwd=root, text=True, capture_output=True, check=False,
            timeout=300,
        )
    except (OSError, subprocess.SubprocessError) as error:
        append_log(log, f"[SENTINELA] {label}_error={error}")
        return 127
    if result.stdout:
        append_log(log, result.stdout)
    if result.stderr:
        append_log(log, result.stderr)
    append_log(log, f"[SENTINELA] {label}_exit={result.returncode}")
    return result.returncode


def validate_installation(root: Path, log: Path) -> int:
    required = (
        "governanca/sentinela_project.json",
        "governanca/tools/sentinela_watch.py",
        "governanca/tools/sentinela_ai.py",
        "governanca/tools/start_sentinela.sh",
        "governanca/tools/status_sentinela.sh",
        "governanca/tools/stop_sentinela.sh",
    )
    missing = [item for item in required if not (root / item).is_file()]
    if missing:
        append_log(log, f"[SENTINELA] installation_missing={','.join(missing)}")
        return 2
    checks = [
        [sys.executable, "-m", "py_compile",
         "governanca/tools/sentinela_watch.py",
         "governanca/tools/sentinela_ai.py"],
        ["bash", "-n", "governanca/tools/start_sentinela.sh",
         "governanca/tools/status_sentinela.sh",
         "governanca/tools/stop_sentinela.sh"],
    ]
    return max(run(command, root, log, "installation") for command in checks)


def check_changed(root: Path, changed: list[str], log: Path) -> dict[str, int]:
    existing = [item for item in changed if (root / item).is_file()]
    groups = {
        "python": [item for item in existing if Path(item).suffix == ".py"],
        "shell": [item for item in existing if Path(item).suffix == ".sh"],
        "r": [item for item in existing if Path(item).suffix in {".R", ".r"}],
    }
    results: dict[str, int] = {}
    if groups["python"]:
        results["python"] = run(
            [sys.executable, "-m", "py_compile", *groups["python"]],
            root, log, "python_syntax",
        )
    if groups["shell"]:
        results["shell"] = run(
            ["bash", "-n", *groups["shell"]], root, log, "shell_syntax",
        )
    for item in groups["r"]:
        code = run(
            ["Rscript", "-e", f"parse(file={json.dumps(item)})"],
            root, log, "r_syntax",
        )
        results[f"r:{item}"] = code
    return results


def enqueue_incident(
    root: Path, project_id: str, changed: list[str], failures: dict[str, int],
) -> None:
    directory = root / "governanca/evidencias/sentinela_ai/incidents"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%z")
    incident_id = f"{stamp}-{uuid.uuid4().hex[:8]}"
    payload = {
        "schema_version": 1,
        "incident_id": incident_id,
        "project_id": project_id,
        "observed_at": now_iso(),
        "changed": changed[:100],
        "failures": failures,
        "constraints": {"analysis_only": True, "automatic_mutation": False},
    }
    (directory / f"{incident_id}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--pid-file", default="governanca/evidencias/.sentinela.pid")
    parser.add_argument("--log", default="governanca/evidencias/sentinela_watch.log")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    config = load_config(root)
    project_id = str(config["project_id"])
    log = root / args.log
    pid_path = root / args.pid_file
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(f"{os.getpid()}\n", encoding="utf-8")
    append_log(log, f"[SENTINELA] started_at={now_iso()} project_id={project_id} root={root}")
    code = validate_installation(root, log)
    if args.once:
        return code
    state = snapshot(root)
    while True:
        time.sleep(max(0.5, args.interval))
        current = snapshot(root)
        changed = [
            item for item in sorted(set(state) | set(current))
            if state.get(item) != current.get(item)
        ]
        if not changed:
            continue
        append_log(log, f"[SENTINELA] changed_at={now_iso()} files={','.join(changed[:30])}")
        failures = {name: value for name, value in check_changed(root, changed, log).items() if value}
        if failures:
            enqueue_incident(root, project_id, changed, failures)
        state = current


if __name__ == "__main__":
    raise SystemExit(main())
