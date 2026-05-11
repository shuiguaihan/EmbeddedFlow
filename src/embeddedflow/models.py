from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class Requirement:
    id: str
    title: str
    evidence: list[str]
    watch: list[str] = field(default_factory=list)
    source: str | None = None
    scope: str | None = None
    tags: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Recipe:
    id: str
    type: str
    description: str
    depends_on: list[str] = field(default_factory=list)
    watch: list[str] = field(default_factory=list)
    review: str | None = None
    command: str | None = None
    working_dir: str | None = None
    env: dict[str, Any] = field(default_factory=dict)
    produces: list[dict[str, Any]] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    timeout: int = 300
    remote: bool = False
    target: str = "default"
    instructions: str | None = None
    path: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SSHConnection:
    host: str
    port: int = 22
    user: str = "root"
    auth_mode: str = "password"
    password_env: str | None = None
    key_path: str | None = None


@dataclass(slots=True)
class EvidenceEvent:
    event: str
    node: str
    req: str
    run: str
    ts: str = field(default_factory=utc_now)
    recipe: str | None = None
    status: str | None = None
    duration_s: float | None = None
    artifacts: list[str] = field(default_factory=list)
    source_hash: str | None = None
    recipe_hash: str | None = None
    depends: list[str] = field(default_factory=list)
    reason: str | None = None
    changed_files: list[str] = field(default_factory=list)
    old_hash: str | None = None
    new_hash: str | None = None
    reviewer: str | None = None
    review_status: str | None = None
    rationale: str | None = None
    conditions: str | None = None
    error: str | None = None
    exit_code: int | None = None
    stderr_tail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for key in self.__dataclass_fields__:  # type: ignore[attr-defined]
            value = getattr(self, key)
            if value is None:
                continue
            if value == []:
                continue
            data[key] = value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvidenceEvent":
        known = {key: data.get(key) for key in cls.__dataclass_fields__ if key in data}  # type: ignore[attr-defined]
        return cls(**known)


@dataclass(slots=True)
class Graph:
    nodes: dict[str, Recipe]
    edges: dict[str, list[str]]
    reverse_edges: dict[str, list[str]]
    required: list[str]
