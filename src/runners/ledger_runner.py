"""Central ledger writer for completed runs."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import secrets

from src.services.concurrency import ReviewerResult


def new_request_id() -> str:
    return f"rev_{secrets.token_hex(2)}"


def append_ledger_entry(
    result: ReviewerResult,
    *,
    request_id: str,
    ledger_path: str | Path = "ledger.jsonl",
) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "request_id": request_id,
        "agent": result.agent_name,
        "ms": result.duration_ms,
        "findings": len(result.findings),
    }
    with Path(ledger_path).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")
