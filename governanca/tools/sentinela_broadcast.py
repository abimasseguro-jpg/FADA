#!/usr/bin/env python3
"""Append portable, consultative mother lessons to child sentinel inboxes."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


INBOX_RELATIVE = Path(
    "governanca/evidencias/sentinela_parent_lessons.jsonl"
)


def canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def lesson_fingerprint(payload: dict[str, Any]) -> str:
    identity = {
        "title": payload.get("title"),
        "principles": payload.get("principles"),
        "schema_version": payload.get("schema_version"),
    }
    return hashlib.sha256(canonical_json(identity).encode()).hexdigest()[:20]


def existing_fingerprints(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    fingerprints: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            fingerprints.add(str(json.loads(line).get("fingerprint") or ""))
        except (ValueError, TypeError):
            continue
    return fingerprints


def append_lesson(child_root: Path, lesson: dict[str, Any]) -> bool:
    root = child_root.resolve()
    governance = root / "governanca"
    if not governance.is_dir():
        raise ValueError(f"child has no governance directory: {root}")
    target = root / INBOX_RELATIVE
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_path = target.parent / ".sentinela_parent_lessons.lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if lesson["fingerprint"] in existing_fingerprints(target):
            return False
        with target.open("a", encoding="utf-8") as stream:
            stream.write(canonical_json(lesson) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-project", required=True)
    parser.add_argument("--target", type=Path, action="append", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--principle", action="append", required=True)
    parser.add_argument("--recommendation", action="append", default=[])
    args = parser.parse_args()
    base = {
        "schema_version": 1,
        "issued_at": now_iso(),
        "source": {
            "project": args.source_project,
            "role": "sentinela_mae",
        },
        "authority": "consultative",
        "automatic_mutation_allowed": False,
        "title": args.title,
        "principles": args.principle,
        "recommendations": args.recommendation,
        "required_response": (
            "Classify as applicable, not_applicable, already_present or "
            "candidate; do not promote automatically."
        ),
    }
    base["fingerprint"] = lesson_fingerprint(base)
    failures = 0
    for target in args.target:
        lesson = {
            **base,
            "destination": {
                "project": target.resolve().name,
                "role": "sentinela_filha",
            },
        }
        try:
            created = append_lesson(target, lesson)
            print(
                f"[SENTINELA_BROADCAST] target={target.resolve().name} "
                f"fingerprint={lesson['fingerprint']} "
                f"created={str(created).lower()}"
            )
        except (OSError, ValueError) as error:
            failures += 1
            print(
                f"[SENTINELA_BROADCAST_ERROR] target={target} error={error}",
                file=sys.stderr,
            )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
