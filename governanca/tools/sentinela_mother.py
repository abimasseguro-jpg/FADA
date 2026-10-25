#!/usr/bin/env python3
"""Durable, append-only intercommunication bridge to the Sentinela-mãe."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import socket
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


MOTHER_RELATIVE = Path("governanca/evidencias/sentinela_mae")
CAPABILITIES_RELATIVE = Path("governanca/sentinela_capabilities.json")
DOMAINS_RELATIVE = Path("governanca/sentinela_document_domains.json")
PROFILES_RELATIVE = Path("governanca/sentinela_profiles.json")
AUDIT_EXCEPTIONS_RELATIVE = Path(
    "governanca/sentinela_audit_exceptions.json"
)
GENESIS_HASH = "0" * 64


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp.{os.getpid()}")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def safe_text(value: object, limit: int = 4000) -> str:
    return str(value).replace("\x00", "")[:limit]


def append_mother_event(
    root: Path,
    *,
    event_type: str,
    severity: str,
    semantic_translation: dict[str, Any],
    payload: dict[str, Any],
) -> Path:
    """Append one hash-chained event for deterministic mother consumption."""
    root = root.resolve()
    directory = root / MOTHER_RELATIVE
    directory.mkdir(parents=True, exist_ok=True)
    lock_path = directory / ".bridge.lock"
    state_path = directory / "state.json"
    events_path = directory / "events.jsonl"
    with lock_path.open("a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        previous_hash = GENESIS_HASH
        sequence = 0
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            previous_hash = str(state.get("last_event_hash") or GENESIS_HASH)
            sequence = int(state.get("sequence") or 0)
        except (OSError, ValueError, TypeError):
            pass
        body = {
            "schema_version": 1,
            "event_id": uuid.uuid4().hex,
            "sequence": sequence + 1,
            "observed_at": now_iso(),
            "source": {
                "machine": socket.gethostname(),
                "project": root.name,
                "project_root": str(root),
                "sentinel_role": "child",
            },
            "destination": "sentinela_mae",
            "event_type": safe_text(event_type, 120),
            "severity": safe_text(severity, 40),
            "semantic_translation": {
                key: safe_text(value)
                for key, value in semantic_translation.items()
            },
            "payload": payload,
            "previous_event_hash": previous_hash,
        }
        event_hash = hashlib.sha256(
            (previous_hash + "\0" + canonical_json(body)).encode()
        ).hexdigest()
        event = {**body, "event_hash": event_hash}
        with events_path.open("a", encoding="utf-8") as stream:
            stream.write(canonical_json(event) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        atomic_json(state_path, {
            "schema_version": 1,
            "sequence": sequence + 1,
            "last_event_hash": event_hash,
            "last_event_at": body["observed_at"],
            "events_path": str(events_path.relative_to(root)),
            "delivery_contract": "append-only-local-mother-intake",
        })
    return events_path


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError:
        return None
    return digest.hexdigest()


def audit_event_chain(root: Path) -> dict[str, Any]:
    """Validate sequence, hashes, required fields and persisted tail state."""
    root = root.resolve()
    directory = root / MOTHER_RELATIVE
    events_path = directory / "events.jsonl"
    state_path = directory / "state.json"
    errors: list[str] = []
    counts: dict[str, int] = {}
    previous_hash = GENESIS_HASH
    expected_sequence = 1
    last_observed_at: str | None = None
    accepted_exceptions: list[dict[str, Any]] = []
    exception_keys: set[tuple[int, str, str]] = set()
    try:
        exception_payload = json.loads(
            (root / AUDIT_EXCEPTIONS_RELATIVE).read_text(encoding="utf-8")
        )
        for item in exception_payload.get("exceptions", []):
            if not isinstance(item, dict) or item.get("approved") is not True:
                continue
            exception_keys.add((
                int(item.get("line")),
                str(item.get("event_hash") or ""),
                str(item.get("rule") or ""),
            ))
    except (OSError, ValueError, TypeError):
        pass
    if events_path.is_file():
        with events_path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                try:
                    event = json.loads(line)
                except (ValueError, TypeError) as error:
                    errors.append(f"line {line_number}: invalid JSON: {error}")
                    continue
                if not isinstance(event, dict):
                    errors.append(f"line {line_number}: event is not an object")
                    continue
                event_type = str(event.get("event_type") or "")
                counts[event_type or "<missing>"] = counts.get(
                    event_type or "<missing>", 0
                ) + 1
                sequence = event.get("sequence")
                if sequence != expected_sequence:
                    errors.append(
                        f"line {line_number}: sequence={sequence}, "
                        f"expected={expected_sequence}"
                    )
                if event.get("previous_event_hash") != previous_hash:
                    errors.append(
                        f"line {line_number}: previous_event_hash mismatch"
                    )
                supplied_hash = str(event.get("event_hash") or "")
                body = {
                    key: value for key, value in event.items()
                    if key != "event_hash"
                }
                calculated_hash = hashlib.sha256(
                    (previous_hash + "\0" + canonical_json(body)).encode()
                ).hexdigest()
                if supplied_hash != calculated_hash:
                    errors.append(f"line {line_number}: event_hash mismatch")
                translation = event.get("semantic_translation")
                if not isinstance(translation, dict) or not translation.get(
                    "summary"
                ):
                    exception_key = (
                        line_number, supplied_hash,
                        "semantic_translation_missing",
                    )
                    if exception_key in exception_keys:
                        accepted_exceptions.append({
                            "line": line_number,
                            "event_hash": supplied_hash,
                            "rule": "semantic_translation_missing",
                        })
                    else:
                        errors.append(
                            f"line {line_number}: semantic translation missing"
                        )
                previous_hash = supplied_hash or calculated_hash
                expected_sequence += 1
                last_observed_at = str(event.get("observed_at") or "")
    else:
        errors.append(f"events file missing: {events_path}")

    event_count = expected_sequence - 1
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as error:
        errors.append(f"invalid state: {error}")
        state = {}
    if state.get("sequence") != event_count:
        errors.append("state sequence does not match event chain")
    if event_count and state.get("last_event_hash") != previous_hash:
        errors.append("state last_event_hash does not match event chain")
    if event_count and state.get("last_event_at") != last_observed_at:
        errors.append("state last_event_at does not match event chain")
    return {
        "valid": not errors,
        "event_count": event_count,
        "last_event_hash": previous_hash if event_count else None,
        "last_event_at": last_observed_at,
        "event_types": dict(sorted(counts.items())),
        "accepted_exceptions": accepted_exceptions,
        "errors": errors,
    }


def audit_capabilities(root: Path) -> dict[str, Any]:
    """Validate the machine-readable capability registry."""
    path = root.resolve() / CAPABILITIES_RELATIVE
    errors: list[str] = []
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as error:
        return {"valid": False, "count": 0, "errors": [str(error)]}
    capabilities = registry.get("capabilities", [])
    portability = registry.get("portability", {})
    if not isinstance(portability, dict):
        errors.append("portability must be an object")
        portability = {}
    if portability.get("absolute_paths_allowed") is not False:
        errors.append("portable registry must forbid absolute paths")
    authority = str(registry.get("authority") or "")
    if not authority or Path(authority).is_absolute():
        errors.append("authority must be a non-empty relative path")
    if not isinstance(capabilities, list):
        return {
            "valid": False,
            "count": 0,
            "errors": ["capabilities must be a list"],
        }
    identifiers: set[str] = set()
    required = {
        "id", "owner", "mode", "status", "effect", "authorization"
    }
    valid_statuses = {"implemented", "partial", "policy_only", "retired"}
    for index, item in enumerate(capabilities):
        if not isinstance(item, dict):
            errors.append(f"capability {index}: not an object")
            continue
        missing = required - set(item)
        if missing:
            errors.append(
                f"capability {index}: missing {','.join(sorted(missing))}"
            )
        identifier = str(item.get("id") or "")
        if not identifier:
            errors.append(f"capability {index}: empty id")
        elif identifier in identifiers:
            errors.append(f"duplicate capability id: {identifier}")
        identifiers.add(identifier)
        if item.get("status") not in valid_statuses:
            errors.append(
                f"capability {identifier or index}: invalid status"
            )
    return {
        "valid": not errors,
        "count": len(capabilities),
        "implemented": sum(
            item.get("status") == "implemented"
            for item in capabilities if isinstance(item, dict)
        ),
        "policy_only": sum(
            item.get("status") == "policy_only"
            for item in capabilities if isinstance(item, dict)
        ),
        "portable": not any(
            error.startswith("portable") or error.startswith("authority")
            for error in errors
        ),
        "errors": errors,
    }


def audit_document_domains(root: Path) -> dict[str, Any]:
    path = root.resolve() / DOMAINS_RELATIVE
    errors: list[str] = []
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as error:
        return {"valid": False, "count": 0, "errors": [str(error)]}
    domains = registry.get("domains", [])
    precedence = registry.get("precedence", [])
    if not isinstance(domains, list):
        errors.append("domains must be a list")
        domains = []
    if not isinstance(precedence, list) or not precedence:
        errors.append("precedence must be a non-empty list")
    identifiers: set[str] = set()
    primaries: dict[str, str] = {}
    for index, item in enumerate(domains):
        if not isinstance(item, dict):
            errors.append(f"domain {index}: not an object")
            continue
        identifier = str(item.get("id") or "")
        primary = str(item.get("primary") or "")
        if not identifier or identifier in identifiers:
            errors.append(f"domain {index}: empty or duplicate id")
        identifiers.add(identifier)
        if not primary or Path(primary).is_absolute():
            errors.append(f"domain {identifier or index}: invalid primary")
        prior = primaries.get(identifier)
        if prior and prior != primary:
            errors.append(f"domain {identifier}: conflicting primary")
        primaries[identifier] = primary
    return {
        "valid": not errors,
        "count": len(domains),
        "precedence_count": len(precedence) if isinstance(precedence, list) else 0,
        "errors": errors,
    }


def audit_profiles(root: Path) -> dict[str, Any]:
    path = root.resolve() / PROFILES_RELATIVE
    errors: list[str] = []
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as error:
        return {"valid": False, "count": 0, "errors": [str(error)]}
    contexts = registry.get("contexts", [])
    profiles = registry.get("profiles", [])
    if not isinstance(contexts, list) or not contexts:
        errors.append("contexts must be a non-empty list")
        contexts = []
    if not isinstance(profiles, list):
        errors.append("profiles must be a list")
        profiles = []
    identifiers: set[str] = set()
    for index, profile in enumerate(profiles):
        if not isinstance(profile, dict):
            errors.append(f"profile {index}: not an object")
            continue
        identifier = str(profile.get("id") or "")
        if not identifier or identifier in identifiers:
            errors.append(f"profile {index}: empty or duplicate id")
        identifiers.add(identifier)
        allowed = profile.get("allowed_contexts", [])
        if not isinstance(allowed, list) or not set(allowed) <= set(contexts):
            errors.append(f"profile {identifier or index}: invalid contexts")
    if registry.get("default_context") not in contexts:
        errors.append("default_context is not declared")
    if registry.get("default_profile") not in identifiers:
        errors.append("default_profile is not declared")
    return {
        "valid": not errors,
        "count": len(profiles),
        "context_count": len(contexts),
        "errors": errors,
    }


def route_document_domain(root: Path, domain: str) -> dict[str, Any]:
    registry = json.loads(
        (root.resolve() / DOMAINS_RELATIVE).read_text(encoding="utf-8")
    )
    for item in registry.get("domains", []):
        if isinstance(item, dict) and item.get("id") == domain:
            return item
    raise ValueError(f"unknown document domain: {domain}")


def resolve_profile(
    root: Path,
    *,
    profile_id: str | None = None,
    context: str | None = None,
    hostname: str | None = None,
) -> dict[str, Any]:
    registry = json.loads(
        (root.resolve() / PROFILES_RELATIVE).read_text(encoding="utf-8")
    )
    profiles = [
        item for item in registry.get("profiles", [])
        if isinstance(item, dict)
    ]
    effective_context = (
        context
        or os.environ.get("SENTINELA_CONTEXT")
        or ("ci" if os.environ.get("CI", "").lower() == "true" else None)
        or registry.get("default_context")
    )
    effective_hostname = hostname or socket.gethostname()
    requested = profile_id or os.environ.get("SENTINELA_MACHINE_PROFILE")
    selected: dict[str, Any] | None = None
    if requested:
        selected = next(
            (item for item in profiles if item.get("id") == requested), None
        )
        if selected is None:
            raise ValueError(f"unknown profile: {requested}")
    if selected is None:
        selected = next(
            (
                item for item in profiles
                if effective_hostname in item.get("hostnames", [])
            ),
            None,
        )
    if selected is None:
        default_profile = registry.get("default_profile")
        selected = next(
            (item for item in profiles if item.get("id") == default_profile),
            None,
        )
    if selected is None:
        raise ValueError("default profile not found")
    allowed = effective_context in selected.get("allowed_contexts", [])
    return {
        "valid": allowed,
        "profile": selected,
        "context": effective_context,
        "hostname": effective_hostname,
        "mismatch": None if allowed else "context_not_allowed",
    }


def audit(root: Path) -> dict[str, Any]:
    chain = audit_event_chain(root)
    capabilities = audit_capabilities(root)
    domains = audit_document_domains(root)
    profiles = audit_profiles(root)
    return {
        "valid": all((
            chain["valid"], capabilities["valid"],
            domains["valid"], profiles["valid"],
        )),
        "root": str(root.resolve()),
        "event_chain": chain,
        "capabilities": capabilities,
        "document_domains": domains,
        "profiles": profiles,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    audit_parser = commands.add_parser(
        "audit", help="validate mother intake and capability registry"
    )
    audit_parser.add_argument("--root", type=Path, default=Path.cwd())
    audit_parser.add_argument("--json", action="store_true")
    route_parser = commands.add_parser(
        "route", help="resolve the primary source for a document domain"
    )
    route_parser.add_argument("--root", type=Path, default=Path.cwd())
    route_parser.add_argument("--domain", required=True)
    profile_parser = commands.add_parser(
        "profile", help="resolve portable machine and execution context"
    )
    profile_parser.add_argument("--root", type=Path, default=Path.cwd())
    profile_parser.add_argument("--profile")
    profile_parser.add_argument("--context")
    profile_parser.add_argument("--hostname")
    args = parser.parse_args()
    if args.command == "route":
        try:
            print(canonical_json(route_document_domain(args.root, args.domain)))
            return 0
        except (OSError, ValueError, TypeError) as error:
            print(f"[SENTINELA_MAE_ERROR] {error}", file=sys.stderr)
            return 2
    if args.command == "profile":
        try:
            resolved = resolve_profile(
                args.root,
                profile_id=args.profile,
                context=args.context,
                hostname=args.hostname,
            )
            print(canonical_json(resolved))
            return 0 if resolved["valid"] else 1
        except (OSError, ValueError, TypeError) as error:
            print(f"[SENTINELA_MAE_ERROR] {error}", file=sys.stderr)
            return 2
    report = audit(args.root)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        chain = report["event_chain"]
        capabilities = report["capabilities"]
        domains = report["document_domains"]
        profiles = report["profiles"]
        print(
            "[SENTINELA_MAE] "
            f"status={'OK' if report['valid'] else 'FALHA'} "
            f"events={chain['event_count']} "
            f"capabilities={capabilities['count']} "
            f"implemented={capabilities.get('implemented', 0)} "
            f"policy_only={capabilities.get('policy_only', 0)} "
            f"domains={domains['count']} profiles={profiles['count']}"
        )
        for error in [
            *chain["errors"], *capabilities["errors"],
            *domains["errors"], *profiles["errors"],
        ]:
            print(f"[SENTINELA_MAE_ERROR] {error}")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
