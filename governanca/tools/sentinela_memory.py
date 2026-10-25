#!/usr/bin/env python3
"""Portable, append-only memory and learning lifecycle for Sentinela-mãe."""
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

from sentinela_mother import append_mother_event, atomic_json, canonical_json


MEMORY_RELATIVE = Path("governanca/evidencias/sentinela_memory")
AI_BACKLOG_RELATIVE = Path(
    "governanca/evidencias/sentinela_ai/learning_backlog.jsonl"
)
MEMORY_CLASSES = {
    "normative", "operational", "causal", "operator_intent", "experimental"
}
DECISIONS = {
    "reviewed", "accepted", "rejected", "implemented", "validated",
    "superseded", "expired",
}
TRANSITIONS = {
    "proposed": {"reviewed", "accepted", "rejected", "expired"},
    "reviewed": {"accepted", "rejected", "expired"},
    "accepted": {"implemented", "superseded"},
    "implemented": {"validated", "superseded"},
    "validated": {"superseded"},
    "rejected": set(),
    "superseded": set(),
    "expired": set(),
}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.is_file():
        return records
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            record = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.parent / ".memory.lock"
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(canonical_json(record) + "\n")
            stream.flush()
            os.fsync(stream.fileno())


def candidate_fingerprint(record: dict[str, Any]) -> str:
    identity = {
        "memory_class": record.get("memory_class"),
        "kind": record.get("kind"),
        "summary": " ".join(str(record.get("summary", "")).split()),
        "scope": record.get("scope"),
    }
    return hashlib.sha256(canonical_json(identity).encode()).hexdigest()[:20]


def all_candidates(root: Path) -> dict[str, dict[str, Any]]:
    root = root.resolve()
    candidates: dict[str, dict[str, Any]] = {}
    local_path = root / MEMORY_RELATIVE / "candidates.jsonl"
    for record in read_jsonl(local_path):
        fingerprint = str(record.get("fingerprint") or "")
        if fingerprint:
            candidates[fingerprint] = record
    for record in read_jsonl(root / AI_BACKLOG_RELATIVE):
        fingerprint = str(record.get("fingerprint") or "")
        if not fingerprint or fingerprint in candidates:
            continue
        candidates[fingerprint] = {
            "schema_version": 1,
            "fingerprint": fingerprint,
            "created_at": record.get("created_at"),
            "memory_class": "experimental",
            "kind": "ai_learning",
            "summary": record.get("change") or record.get("artifact"),
            "scope": record.get("artifact") or "project",
            "source": {
                "type": "sentinela_ai",
                "incident_id": record.get("incident_id"),
                "incident_kind": record.get("incident_kind"),
            },
            "evidence": record.get("validation"),
            "expires": None,
            "origin": "sentinela_ai_learning_backlog",
        }
    return candidates


def review_state(root: Path) -> dict[str, dict[str, Any]]:
    reviews_path = root.resolve() / MEMORY_RELATIVE / "reviews.jsonl"
    states: dict[str, dict[str, Any]] = {}
    for record in read_jsonl(reviews_path):
        fingerprint = str(record.get("fingerprint") or "")
        if fingerprint:
            states[fingerprint] = record
    return states


def status_report(root: Path) -> dict[str, Any]:
    candidates = all_candidates(root)
    reviews = review_state(root)
    by_state: dict[str, int] = {}
    by_class: dict[str, int] = {}
    for fingerprint, candidate in candidates.items():
        state = str(reviews.get(fingerprint, {}).get("decision") or "proposed")
        memory_class = str(candidate.get("memory_class") or "experimental")
        by_state[state] = by_state.get(state, 0) + 1
        by_class[memory_class] = by_class.get(memory_class, 0) + 1
    orphan_reviews = sorted(set(reviews) - set(candidates))
    return {
        "valid": not orphan_reviews,
        "candidate_count": len(candidates),
        "review_count": len(reviews),
        "states": dict(sorted(by_state.items())),
        "classes": dict(sorted(by_class.items())),
        "orphan_reviews": orphan_reviews,
    }


def record_candidate(
    root: Path,
    *,
    memory_class: str,
    kind: str,
    summary: str,
    scope: str,
    source: str,
    evidence: str,
    expires: str | None,
) -> tuple[dict[str, Any], bool]:
    if memory_class not in MEMORY_CLASSES:
        raise ValueError(f"invalid memory class: {memory_class}")
    candidate = {
        "schema_version": 1,
        "created_at": now_iso(),
        "memory_class": memory_class,
        "kind": kind,
        "summary": summary,
        "scope": scope,
        "source": {"type": source},
        "evidence": evidence,
        "expires": expires,
        "origin": "session_capture",
    }
    candidate["fingerprint"] = candidate_fingerprint(candidate)
    if candidate["fingerprint"] in all_candidates(root):
        return candidate, False
    append_jsonl(
        root.resolve() / MEMORY_RELATIVE / "candidates.jsonl", candidate
    )
    append_mother_event(
        root,
        event_type="memory_candidate_recorded",
        severity="info",
        semantic_translation={
            "summary": "Novo sinal foi registrado para revisão de memória.",
            "operational_meaning": (
                "O sinal permanece proposto e não altera normas ou campanha."
            ),
            "scientific_risk": "Depende da classe, evidência e revisão.",
            "required_response": "Revisar, aceitar, rejeitar ou expirar.",
        },
        payload={
            "fingerprint": candidate["fingerprint"],
            "memory_class": memory_class,
            "kind": kind,
            "scope": scope,
        },
    )
    return candidate, True


def review_candidate(
    root: Path,
    *,
    fingerprint: str,
    decision: str,
    reason: str,
    reviewer: str,
    evidence: str,
) -> dict[str, Any]:
    if decision not in DECISIONS:
        raise ValueError(f"invalid decision: {decision}")
    candidates = all_candidates(root)
    if fingerprint not in candidates:
        raise ValueError(f"unknown fingerprint: {fingerprint}")
    previous = review_state(root).get(fingerprint, {})
    previous_state = str(previous.get("decision") or "proposed")
    if decision not in TRANSITIONS.get(previous_state, set()):
        raise ValueError(
            f"invalid transition: {previous_state} -> {decision}"
        )
    review = {
        "schema_version": 1,
        "reviewed_at": now_iso(),
        "fingerprint": fingerprint,
        "previous_state": previous_state,
        "decision": decision,
        "reason": reason,
        "reviewer": reviewer,
        "evidence": evidence,
    }
    append_jsonl(root.resolve() / MEMORY_RELATIVE / "reviews.jsonl", review)
    append_mother_event(
        root,
        event_type="memory_candidate_reviewed",
        severity="info",
        semantic_translation={
            "summary": f"Memória revisada: {previous_state} → {decision}.",
            "operational_meaning": (
                "A decisão foi preservada; implementação continua separada."
            ),
            "scientific_risk": "Limitado ao escopo declarado da memória.",
            "required_response": (
                "Executar a próxima transição somente com evidência adequada."
            ),
        },
        payload={
            "fingerprint": fingerprint,
            "previous_state": previous_state,
            "decision": decision,
            "reviewer": reviewer,
        },
    )
    return review


def export_inputs(root: Path) -> Path:
    root = root.resolve()
    candidates = all_candidates(root)
    reviews = review_state(root)
    eligible = []
    for fingerprint, candidate in candidates.items():
        review = reviews.get(fingerprint, {})
        state = str(review.get("decision") or "proposed")
        if state not in {"accepted", "implemented", "validated"}:
            continue
        eligible.append({
            **candidate,
            "state": state,
            "review": review,
        })
    target = root / MEMORY_RELATIVE / "sentinela_inputs.json"
    atomic_json(target, {
        "schema_version": 1,
        "generated_at": now_iso(),
        "count": len(eligible),
        "memories": eligible,
    })
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    status = commands.add_parser("status")
    status.add_argument("--root", type=Path, default=Path.cwd())
    status.add_argument("--json", action="store_true")

    record = commands.add_parser("record")
    record.add_argument("--root", type=Path, default=Path.cwd())
    record.add_argument("--class", dest="memory_class", choices=sorted(MEMORY_CLASSES), required=True)
    record.add_argument("--kind", required=True)
    record.add_argument("--summary", required=True)
    record.add_argument("--scope", default="project")
    record.add_argument("--source", default="operator")
    record.add_argument("--evidence", default="")
    record.add_argument("--expires")

    review = commands.add_parser("review")
    review.add_argument("--root", type=Path, default=Path.cwd())
    review.add_argument("--fingerprint", required=True)
    review.add_argument("--decision", choices=sorted(DECISIONS), required=True)
    review.add_argument("--reason", required=True)
    review.add_argument("--reviewer", default=os.environ.get("USER", "operator"))
    review.add_argument("--evidence", default="")

    export = commands.add_parser("export")
    export.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()

    try:
        if args.command == "status":
            report = status_report(args.root)
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
            else:
                states = " ".join(
                    f"{key}={value}" for key, value in report["states"].items()
                )
                print(
                    f"[SENTINELA_MEMORY] status={'OK' if report['valid'] else 'FALHA'} "
                    f"candidates={report['candidate_count']} "
                    f"reviews={report['review_count']} {states}"
                )
            return 0 if report["valid"] else 1
        if args.command == "record":
            candidate, created = record_candidate(
                args.root,
                memory_class=args.memory_class,
                kind=args.kind,
                summary=args.summary,
                scope=args.scope,
                source=args.source,
                evidence=args.evidence,
                expires=args.expires,
            )
            print(
                f"[SENTINELA_MEMORY] fingerprint={candidate['fingerprint']} "
                f"created={str(created).lower()}"
            )
            return 0
        if args.command == "review":
            result = review_candidate(
                args.root,
                fingerprint=args.fingerprint,
                decision=args.decision,
                reason=args.reason,
                reviewer=args.reviewer,
                evidence=args.evidence,
            )
            print(
                f"[SENTINELA_MEMORY] fingerprint={result['fingerprint']} "
                f"state={result['decision']}"
            )
            return 0
        target = export_inputs(args.root)
        print(f"[SENTINELA_MEMORY] exported={target}")
        return 0
    except ValueError as error:
        print(f"[SENTINELA_MEMORY_ERROR] {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
