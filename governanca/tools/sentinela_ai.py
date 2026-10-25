#!/usr/bin/env python3
"""Explicit, read-only mAI consultation and incident status."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path


CONTEXT_CANDIDATES = (
    "PROJECT_CONTEXT.md", "README.md", "AGENTS.md",
    "ARCHITECTURE_DECISION_RECORD.md", "DESCRIPTION", "pyproject.toml",
    "governanca/sentinela_project.json",
)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def config(root: Path) -> dict[str, object]:
    payload = json.loads(
        (root / "governanca/sentinela_project.json").read_text(encoding="utf-8")
    )
    if not isinstance(payload, dict) or not payload.get("project_id"):
        raise ValueError("invalid Sentinela project identity")
    return payload


def context(root: Path, budget: int = 60_000) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for relative in CONTEXT_CANDIDATES:
        path = root / relative
        if not path.is_file() or budget <= 0:
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        content = raw[:budget]
        budget -= len(content)
        result.append({
            "path": relative,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "content": content,
        })
    return result


def evidence_counts(root: Path) -> tuple[int, int]:
    base = root / "governanca/evidencias/sentinela_ai"
    incidents = len(list((base / "incidents").glob("*.json"))) if (base / "incidents").is_dir() else 0
    reports = len(list((base / "reports").glob("*.md"))) if (base / "reports").is_dir() else 0
    return incidents, reports


def status(root: Path) -> int:
    identity = config(root)
    incidents, reports = evidence_counts(root)
    print(
        f"[mAI] project_id={identity['project_id']} mode=read-only "
        f"incidents={incidents} reports={reports} codex={'yes' if shutil.which('codex') else 'no'}"
    )
    return 0 if shutil.which("codex") else 1


def consult(root: Path, question: str) -> Path:
    identity = config(root)
    packet = {
        "project_id": identity["project_id"],
        "captured_at": now_iso(),
        "question": question,
        "sources": context(root),
        "constraints": {
            "read_only": True,
            "no_tools": True,
            "no_mutation": True,
            "recommendation_is_not_authorization": True,
        },
    }
    prompt = (
        "Você é a mAI consultiva deste projeto. Analise somente o pacote de "
        "evidências fornecido. Separe fatos, inferências, hipóteses e "
        "desconhecidos; proponha testes falsificáveis e riscos. Não altere "
        "estado e não trate recomendação como autorização. Responda em "
        "português.\n\n" + json.dumps(packet, ensure_ascii=False, indent=2)
    )
    output_dir = root / "governanca/evidencias/sentinela_ai/reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%z")
    output = output_dir / f"consulta_{stamp}.md"
    codex = os.environ.get("SENTINELA_CODEX", "codex")
    with tempfile.TemporaryDirectory(prefix=f"{identity['project_id']}-mai-") as sandbox:
        process = subprocess.run(
            [codex, "exec", "--sandbox", "read-only", "--skip-git-repo-check",
             "--ephemeral", "--color", "never", "-C", sandbox, "-"],
            input=prompt, text=True, capture_output=True, timeout=300, check=False,
        )
    output.write_text(
        f"# Consulta mAI — {identity['project_id']}\n\n{process.stdout}\n\n"
        f"---\n`exit_code={process.returncode}`\n",
        encoding="utf-8",
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "consult"))
    parser.add_argument("question", nargs="?")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command == "status":
        return status(root)
    if not args.question:
        parser.error("consult requires a question")
    print(consult(root, args.question))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
