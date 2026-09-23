from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class TimelineEntry:
    request_id: str
    timestamp: str
    event: str
    agent_name: str
    details: str


class AuditTimeline:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(__file__).resolve().parent.parent / "audit_timeline.jsonl"
        self.request_id = uuid4().hex

    def record(self, event: str, agent_name: str, details: str = "") -> None:
        entry = TimelineEntry(
            self.request_id,
            datetime.now(timezone.utc).isoformat(),
            event,
            agent_name,
            details,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
