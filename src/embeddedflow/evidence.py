from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .models import EvidenceEvent


class EvidenceStore:
    def __init__(self, path: Path):
        self.path = path

    def append(self, event: EvidenceEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a+", encoding="utf-8") as handle:
            try:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            except (ImportError, OSError):
                pass
            handle.write(json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            try:
                import os

                os.fsync(handle.fileno())
            except OSError:
                pass
            try:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except (ImportError, OSError):
                pass

    def read_all(self) -> list[EvidenceEvent]:
        if not self.path.exists():
            return []
        events: list[EvidenceEvent] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            events.append(EvidenceEvent.from_dict(json.loads(line)))
        return events

    def list_events(
        self,
        req: str | None = None,
        node: str | None = None,
        status: str | None = None,
        run: str | None = None,
    ) -> list[EvidenceEvent]:
        events = self.read_all()
        if req is not None:
            events = [event for event in events if event.req == req]
        if node is not None:
            events = [event for event in events if event.node == node]
        if status is not None and status != "all":
            events = [event for event in events if event.status == status or event.event == status]
        if run is not None:
            events = [event for event in events if event.run == run]
        return events

    def latest_event(self, node: str, req: str) -> EvidenceEvent | None:
        events = [event for event in self.list_events(req=req, node=node) if event.event != "reviewed"]
        return events[-1] if events else None

    def latest_review(self, node: str, req: str, after_ts: str | None = None) -> EvidenceEvent | None:
        reviews = [event for event in self.list_events(req=req, node=node) if event.event == "reviewed"]
        if after_ts is not None:
            reviews = [event for event in reviews if event.ts >= after_ts]
        return reviews[-1] if reviews else None
