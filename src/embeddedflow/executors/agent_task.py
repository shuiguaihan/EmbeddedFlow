from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from ..loaders import load_requirement
from ..models import Recipe
from ..template import render_template
from .base import ExecutionResult


def execute_agent_task(root: Path, req_id: str, recipe: Recipe, config: dict[str, Any]) -> ExecutionResult:
    start = time.monotonic()
    agent_config = recipe.raw.get("agent_task")
    if not isinstance(agent_config, dict):
        return ExecutionResult(status="fail", error="agent_task config missing", exit_code=2)

    context_query = agent_config.get("context_query")
    if not isinstance(context_query, str) or not context_query.strip():
        return ExecutionResult(status="fail", error="agent_task context_query missing", exit_code=2)

    instructions_template = agent_config.get("instructions")
    if not isinstance(instructions_template, str) or not instructions_template.strip():
        return ExecutionResult(status="fail", error="agent_task instructions missing", exit_code=2)

    render_context = _render_context(root, req_id, recipe, config)
    try:
        rendered_query = render_template(context_query, render_context)
        rendered_instructions = render_template(instructions_template, render_context)
        output_path = _render_output_path(root, agent_config.get("output_path"), render_context)
    except Exception as exc:
        return ExecutionResult(status="fail", error=str(exc), exit_code=2)

    try:
        proc = subprocess.run(
            rendered_query,
            cwd=root,
            shell=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=recipe.timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stderr = _timeout_text(exc.stderr)
        return ExecutionResult(
            status="fail",
            duration_s=time.monotonic() - start,
            exit_code=124,
            error="context query timeout",
            stderr_tail=stderr[-500:],
        )

    if proc.returncode != 0:
        return ExecutionResult(
            status="fail",
            duration_s=time.monotonic() - start,
            exit_code=proc.returncode,
            error="context query failed",
            stderr_tail=proc.stderr[-500:],
        )

    try:
        context_json = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return ExecutionResult(
            status="fail",
            duration_s=time.monotonic() - start,
            exit_code=1,
            error=f"context query returned invalid JSON: {exc}",
        )

    artifact_dir = root / ".ef" / "artifacts" / req_id / recipe.id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    instructions_path = artifact_dir / "instructions.md"
    context_path = artifact_dir / "context.json"
    instructions_path.write_text(rendered_instructions, encoding="utf-8")
    context_path.write_text(json.dumps(context_json, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    return ExecutionResult(
        status="pass",
        artifacts=[_artifact_text(root, instructions_path), _artifact_text(root, context_path)],
        duration_s=time.monotonic() - start,
        exit_code=0,
    )


def _render_context(root: Path, req_id: str, recipe: Recipe, config: dict[str, Any]) -> dict[str, Any]:
    requirement = load_requirement(root, req_id)
    context = dict(config)
    context["req"] = {
        "id": requirement.id,
        "title": requirement.title,
        "source": requirement.source,
        "scope": requirement.scope,
        "tags": requirement.tags,
        "watch": requirement.watch,
        **requirement.raw,
    }
    context["recipe"] = {"id": recipe.id, "type": recipe.type, **recipe.raw}
    return context


def _render_output_path(root: Path, value: Any, context: dict[str, Any]) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("agent_task output_path must be a non-empty string")
    rendered = Path(render_template(value, context))
    return rendered if rendered.is_absolute() else root / rendered


def _artifact_text(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _timeout_text(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value
