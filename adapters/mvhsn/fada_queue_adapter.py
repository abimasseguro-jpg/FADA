"""MVHSN HTTP queue adapter for the active FADA dispatcher."""

from __future__ import annotations

import json
from urllib.request import Request, urlopen

from fada.dispatcher import QueueBackend


class MVHSNQueueAdapter(QueueBackend):
    """Claim through the authenticated MVHSN coordinator and fail closed."""

    def __init__(self, base_url: str, token: str, *, timeout: float = 10.0) -> None:
        if not base_url.startswith("http://") and not base_url.startswith("https://"):
            raise ValueError("queue URL must be HTTP(S)")
        if not token:
            raise ValueError("queue token is required")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.capabilities: dict[str, object] = {}

    def set_capabilities(self, capabilities: dict[str, object]) -> None:
        if not isinstance(capabilities, dict) or not capabilities:
            raise ValueError("capabilities are required before claiming")
        self.capabilities = dict(capabilities)

    def claim(self, task_id: str, worker_id: str, idempotency_key: str) -> bool:
        if not self.capabilities:
            raise RuntimeError("set_capabilities must be called before claim")
        machine = worker_id.split(":", 1)[0]
        request = Request(
            self.base_url + "/claim",
            data=json.dumps({
                "machine": machine, "worker_id": worker_id,
                "task_key": task_id, "idempotency_key": idempotency_key,
                "capabilities": self.capabilities,
            }).encode(),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }, method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read())
        lease = payload.get("lease") if isinstance(payload, dict) else None
        return bool(payload.get("claimed")) and isinstance(lease, dict) and lease.get("task_key") == task_id

    def status(self) -> dict[str, object]:
        request = Request(
            self.base_url + "/status",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read())
        if not isinstance(payload, dict):
            raise RuntimeError("queue status response is not an object")
        return payload
