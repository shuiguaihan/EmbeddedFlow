from __future__ import annotations

import copy
import importlib.util
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from typing import Any

from ..models import Recipe
from .base import ExecutionResult


def execute_python(root: Path, req_id: str, recipe: Recipe, config: dict[str, Any]) -> ExecutionResult:
    start = time.monotonic()
    plugin_name = recipe.raw.get("plugin", recipe.id)
    if not isinstance(plugin_name, str) or not plugin_name:
        return ExecutionResult(status="fail", error="plugin name missing", exit_code=2)

    plugin_path = root / ".ef" / "plugins" / f"{plugin_name}.py"
    if not plugin_path.is_file():
        return ExecutionResult(status="fail", error=f"plugin not found: {plugin_path}", exit_code=2)

    try:
        module = _load_plugin(plugin_name, plugin_path)
        run = getattr(module, "run", None)
        if not callable(run):
            return ExecutionResult(status="fail", error="plugin missing callable run", exit_code=2)
        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(run, root, req_id, recipe, copy.deepcopy(config))
        try:
            payload = future.result(timeout=recipe.timeout)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
    except TimeoutError:
        return ExecutionResult(status="fail", duration_s=time.monotonic() - start, exit_code=124, error="plugin timeout")
    except Exception as exc:
        return ExecutionResult(status="fail", duration_s=time.monotonic() - start, exit_code=1, error=str(exc))

    if not isinstance(payload, dict):
        return ExecutionResult(status="fail", duration_s=time.monotonic() - start, exit_code=2, error="plugin returned non-dict result")
    status = payload.get("status")
    if status not in {"pass", "fail"}:
        return ExecutionResult(status="fail", duration_s=time.monotonic() - start, exit_code=2, error="plugin result status must be pass or fail")

    artifacts = payload.get("artifacts", [])
    if not isinstance(artifacts, list) or not all(isinstance(item, str) for item in artifacts):
        return ExecutionResult(status="fail", duration_s=time.monotonic() - start, exit_code=2, error="plugin result artifacts must be a list of strings")

    error = payload.get("error")
    if error is not None and not isinstance(error, str):
        error = str(error)
    exit_code = payload.get("exit_code")
    if not isinstance(exit_code, int):
        exit_code = 0 if status == "pass" else 1

    return ExecutionResult(
        status=status,
        artifacts=artifacts,
        duration_s=time.monotonic() - start,
        exit_code=exit_code,
        error=error,
    )


def _load_plugin(plugin_name: str, plugin_path: Path):
    spec = importlib.util.spec_from_file_location(f"embeddedflow_plugin_{plugin_name}", plugin_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load plugin: {plugin_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
