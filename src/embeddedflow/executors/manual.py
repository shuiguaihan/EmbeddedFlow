from __future__ import annotations

from pathlib import Path

from ..models import Recipe
from .base import ExecutionResult


def execute_manual(root: Path, req_id: str, recipe: Recipe) -> ExecutionResult:
    artifact_dir = root / ".ef" / "artifacts" / req_id / recipe.id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    instructions = recipe.instructions or recipe.description
    (artifact_dir / "instructions.txt").write_text(instructions + "\n", encoding="utf-8")
    return ExecutionResult(status="pass", artifacts=[str((artifact_dir / "instructions.txt").relative_to(root))])
