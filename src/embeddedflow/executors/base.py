from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ExecutionResult:
    status: str
    artifacts: list[str] = field(default_factory=list)
    duration_s: float = 0.0
    exit_code: int | None = None
    error: str | None = None
    stderr_tail: str | None = None
