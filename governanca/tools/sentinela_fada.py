#!/usr/bin/env python3
"""Deterministic guardian for the FADA scheduling project."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from sentinela_mother import append_mother_event, atomic_json, audit


REQUIRED = (
    "README.md",
    "pyproject.toml",
    "docs/SPECIFICATION.md",
    "governanca/SENTINELA_FADA.md",
    "governanca/VALIDATION_GATES.md",
    "src/fada/policy.py",
    "tests/test_policy.py",
)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def initialize(root: Path) -> bool:
    root = root.resolve()
    state = root / "governanca/evidencias/sentinela_mae/state.json"
    if state.is_file():
        return False
    append_mother_event(
        root,
        event_type="child_sentinel_registered",
        severity="info",
        semantic_translation={
            "summary": "A Sentinela-FADA foi criada e filiada ao Sentinela-mãe.",
            "operational_meaning": "A FADA possui governança e auditoria próprias.",
            "scientific_risk": "Nenhuma política foi promovida para produção.",
            "required_response": "Preservar a filiação e auditar antes de promoção.",
        },
        payload={
            "child": "FADA",
            "authority": "governanca/SENTINELA_FADA.md",
            "production_mutation_allowed": False,
        },
    )
    return True


def run_tests(root: Path) -> dict[str, Any]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(root / "src")
    process = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=root,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "valid": process.returncode == 0,
        "returncode": process.returncode,
        "output": (process.stdout + process.stderr)[-8000:],
    }


def audit_fada(root: Path, *, with_tests: bool) -> dict[str, Any]:
    root = root.resolve()
    mother = audit(root)
    missing = [relative for relative in REQUIRED if not (root / relative).exists()]
    specification = (root / "docs/SPECIFICATION.md").read_text(
        encoding="utf-8", errors="replace"
    ) if not missing else ""
    required_concepts = ["fallback", "Sufferage", "epsilon", "rollback"]
    absent_concepts = [item for item in required_concepts if item not in specification]
    tests = run_tests(root) if with_tests else {"valid": True, "skipped": True}
    valid = mother["valid"] and not missing and not absent_concepts and tests["valid"]
    return {
        "valid": valid,
        "root": str(root),
        "mother_contract": mother,
        "missing_required_files": missing,
        "missing_specification_concepts": absent_concepts,
        "tests": tests,
    }


def record_incident(
    root: Path, *, title: str, severity: str, summary: str,
    facts: list[str], inference: str, alternatives: list[str],
    conclusion_state: str,
) -> Path:
    root = root.resolve()
    identifier = datetime.now().strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    target = root / "governanca/evidencias/incidents" / f"{identifier}.json"
    payload = {
        "schema_version": 1,
        "incident_id": identifier,
        "observed_at": now_iso(),
        "title": title,
        "severity": severity,
        "summary": summary,
        "facts": facts,
        "inference": inference,
        "assumptions": [],
        "unknowns": [],
        "alternative_explanations": alternatives,
        "falsification_tests": [],
        "causal_boundary": "Somente os fatos registrados são demonstrados.",
        "conclusion_state": conclusion_state,
        "status": "open",
    }
    atomic_json(target, payload)
    append_mother_event(
        root,
        event_type="incident_observed",
        severity=severity,
        semantic_translation={
            "summary": summary,
            "operational_meaning": "Incidente FADA aberto para estudo epistemológico.",
            "scientific_risk": "Depende do escopo e da evidência registrada.",
            "required_response": "Investigar, falsificar alternativas e validar solução.",
        },
        payload={
            "incident_id": identifier,
            "title": title,
            "conclusion_state": conclusion_state,
            "evidence": str(target.relative_to(root)),
        },
    )
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "status"):
        item = commands.add_parser(name)
        item.add_argument("--root", type=Path, default=Path.cwd())
    audit_parser = commands.add_parser("audit")
    audit_parser.add_argument("--root", type=Path, default=Path.cwd())
    audit_parser.add_argument("--skip-tests", action="store_true")
    audit_parser.add_argument("--json", action="store_true")
    incident = commands.add_parser("incident")
    incident.add_argument("--root", type=Path, default=Path.cwd())
    incident.add_argument("--title", required=True)
    incident.add_argument("--severity", choices=("info", "warning", "error", "critical"), required=True)
    incident.add_argument("--summary", required=True)
    incident.add_argument("--fact", action="append", default=[])
    incident.add_argument("--inference", default="")
    incident.add_argument("--alternative", action="append", default=[])
    incident.add_argument("--conclusion-state", choices=("demonstrated", "provisional", "undetermined"), default="undetermined")
    args = parser.parse_args()

    if args.command == "init":
        created = initialize(args.root)
        print(f"[SENTINELA_FADA] initialized={str(created).lower()}")
        return 0
    if args.command == "incident":
        target = record_incident(
            args.root, title=args.title, severity=args.severity,
            summary=args.summary, facts=args.fact, inference=args.inference,
            alternatives=args.alternative, conclusion_state=args.conclusion_state,
        )
        print(f"[SENTINELA_FADA] incident={target}")
        return 0
    report = audit_fada(args.root, with_tests=False if args.command == "status" else not args.skip_tests)
    if getattr(args, "json", False):
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        chain = report["mother_contract"]["event_chain"]
        print(
            f"[SENTINELA_FADA] status={'OK' if report['valid'] else 'FALHA'} "
            f"events={chain['event_count']} tests={'skip' if report['tests'].get('skipped') else report['tests']['returncode']}"
        )
        for error in report["missing_required_files"] + report["missing_specification_concepts"]:
            print(f"[SENTINELA_FADA_ERROR] {error}")
        for section in ("event_chain", "capabilities", "document_domains", "profiles"):
            for error in report["mother_contract"][section]["errors"]:
                print(f"[SENTINELA_FADA_ERROR] {error}")
        if not report["tests"]["valid"]:
            print(report["tests"]["output"])
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())

