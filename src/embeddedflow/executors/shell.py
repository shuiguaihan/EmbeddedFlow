from __future__ import annotations

import os
import re
import shutil
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any

from ..config import load_project_config, resolve_connection
from ..models import Recipe, SSHConnection
from ..template import render_template, render_value
from .base import ExecutionResult


def execute_shell(root: Path, req_id: str, recipe: Recipe, config: dict[str, Any] | None = None) -> ExecutionResult:
    context = config if config is not None else load_project_config(root)
    artifact_dir = root / ".ef" / "artifacts" / req_id / recipe.id
    artifact_dir.mkdir(parents=True, exist_ok=True)

    if recipe.steps:
        return _execute_steps(root, req_id, recipe, context, artifact_dir)
    if not recipe.command:
        return ExecutionResult(status="fail", exit_code=2, error="shell recipe missing command")
    if recipe.remote:
        return _execute_remote(root, req_id, recipe, context, artifact_dir)
    return _execute_local(root, recipe, context, artifact_dir)


def _execute_local(root: Path, recipe: Recipe, context: dict[str, Any], artifact_dir: Path) -> ExecutionResult:
    command = render_template(recipe.command or "", context)
    cwd = _local_cwd(root, recipe, context)
    env = _local_env(recipe, context)
    start = time.monotonic()
    try:
        proc = _run_local_command(command, cwd, env, recipe.timeout)
        duration = time.monotonic() - start
    except subprocess.TimeoutExpired as exc:
        stderr = _timeout_text(exc.stderr)
        stdout = _timeout_text(exc.stdout)
        _write_stream_logs(artifact_dir, stdout, stderr)
        return ExecutionResult(status="fail", duration_s=recipe.timeout, exit_code=124, error="timeout", stderr_tail=stderr[-500:])

    _write_stream_logs(artifact_dir, proc.stdout, proc.stderr)
    artifacts = _base_artifacts(root, artifact_dir)
    artifacts.extend(_existing_produced_artifacts(root, recipe, context))
    if proc.returncode != 0:
        return ExecutionResult(
            status="fail",
            artifacts=artifacts,
            duration_s=duration,
            exit_code=proc.returncode,
            error="command failed",
            stderr_tail=proc.stderr[-500:],
        )
    return ExecutionResult(status="pass", artifacts=artifacts, duration_s=duration, exit_code=0)


def _execute_remote(
    root: Path,
    req_id: str,
    recipe: Recipe,
    context: dict[str, Any],
    artifact_dir: Path,
) -> ExecutionResult:
    conn = _resolve_connection(context, recipe.target)
    command = render_template(recipe.command or "", context)
    remote_command = _remote_shell_command(recipe, context, command)
    ssh_args, env = _ssh_args(conn)
    start = time.monotonic()
    try:
        proc = subprocess.run(
            [*ssh_args, _remote_host(conn), "bash", "-lc", shlex.quote(remote_command)],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=recipe.timeout,
        )
        duration = time.monotonic() - start
    except subprocess.TimeoutExpired as exc:
        stderr = _timeout_text(exc.stderr)
        stdout = _timeout_text(exc.stdout)
        _write_stream_logs(artifact_dir, stdout, stderr)
        return ExecutionResult(status="fail", duration_s=recipe.timeout, exit_code=124, error="timeout", stderr_tail=stderr[-500:])

    _write_stream_logs(artifact_dir, proc.stdout, proc.stderr)
    artifacts = _base_artifacts(root, artifact_dir)
    if proc.returncode != 0:
        return ExecutionResult(
            status="fail",
            artifacts=artifacts,
            duration_s=duration,
            exit_code=proc.returncode,
            error="command failed",
            stderr_tail=proc.stderr[-500:],
        )

    try:
        artifacts.extend(_pull_declared_artifacts(root, recipe, context, conn, artifact_dir))
    except RuntimeError as exc:
        return ExecutionResult(
            status="fail",
            artifacts=artifacts,
            duration_s=time.monotonic() - start,
            exit_code=1,
            error=str(exc),
            stderr_tail=str(exc)[-500:],
        )
    return ExecutionResult(status="pass", artifacts=artifacts, duration_s=duration, exit_code=0)


def _execute_steps(
    root: Path,
    req_id: str,
    recipe: Recipe,
    context: dict[str, Any],
    artifact_dir: Path,
) -> ExecutionResult:
    conn = _resolve_connection(context, recipe.target) if recipe.remote else None
    artifacts = _base_artifacts(root, artifact_dir)
    start = time.monotonic()
    failed = False
    exit_code = 0
    error: str | None = None
    stderr_tail: str | None = None

    for index, step in enumerate(recipe.steps, start=1):
        name = str(step.get("name") or f"step{index}")
        log_path = artifact_dir / f"step_{_safe_step_name(name)}.log"
        artifacts.append(_artifact_text(root, log_path))
        result = _execute_step(root, recipe, context, conn, step, log_path)
        if result.status == "pass":
            continue
        if bool(step.get("ignore_failure", False)):
            continue
        failed = True
        exit_code = result.exit_code or 1
        error = result.error or f"step failed: {name}"
        stderr_tail = result.stderr_tail
        break

    duration = time.monotonic() - start
    if failed:
        return ExecutionResult(
            status="fail",
            artifacts=artifacts,
            duration_s=duration,
            exit_code=exit_code,
            error=error,
            stderr_tail=stderr_tail,
        )

    if recipe.remote and conn is not None:
        try:
            artifacts.extend(_pull_declared_artifacts(root, recipe, context, conn, artifact_dir))
        except RuntimeError as exc:
            return ExecutionResult(
                status="fail",
                artifacts=artifacts,
                duration_s=time.monotonic() - start,
                exit_code=1,
                error=str(exc),
                stderr_tail=str(exc)[-500:],
            )
    else:
        artifacts.extend(_existing_produced_artifacts(root, recipe, context))
    return ExecutionResult(status="pass", artifacts=artifacts, duration_s=duration, exit_code=0)


def _execute_step(
    root: Path,
    recipe: Recipe,
    context: dict[str, Any],
    conn: SSHConnection | None,
    step: dict[str, Any],
    log_path: Path,
) -> ExecutionResult:
    retry = step.get("retry") if isinstance(step.get("retry"), dict) else {}
    attempts = retry.get("max_attempts", 1)
    interval = retry.get("interval_seconds", 0)
    attempts = attempts if isinstance(attempts, int) and attempts > 0 else 1
    interval = interval if isinstance(interval, (int, float)) and interval > 0 else 0
    timeout = step.get("timeout", recipe.timeout)
    timeout = timeout if isinstance(timeout, int) else recipe.timeout

    last_result = ExecutionResult(status="fail", exit_code=1, error="step did not run")
    for attempt in range(1, attempts + 1):
        if step.get("type") == "scp":
            last_result = _execute_scp_step(root, context, conn, step, log_path, attempt, attempts)
        else:
            command = step.get("command")
            if not isinstance(command, str) or not command:
                last_result = ExecutionResult(status="fail", exit_code=2, error="step missing command")
                _append_step_log(log_path, attempt, attempts, "", "", "step missing command")
            elif conn is not None:
                last_result = _execute_remote_step(recipe, context, conn, command, timeout, log_path, attempt, attempts)
            else:
                last_result = _execute_local_step(root, recipe, context, command, timeout, log_path, attempt, attempts)

        if last_result.status == "pass":
            return last_result
        if attempt < attempts and interval:
            time.sleep(interval)
    return last_result


def _execute_local_step(
    root: Path,
    recipe: Recipe,
    context: dict[str, Any],
    command_template: str,
    timeout: int,
    log_path: Path,
    attempt: int,
    attempts: int,
) -> ExecutionResult:
    command = render_template(command_template, context)
    try:
        proc = _run_local_command(command, _local_cwd(root, recipe, context), _local_env(recipe, context), timeout)
    except subprocess.TimeoutExpired as exc:
        stderr = _timeout_text(exc.stderr)
        stdout = _timeout_text(exc.stdout)
        _append_step_log(log_path, attempt, attempts, command, stdout, stderr)
        return ExecutionResult(status="fail", exit_code=124, error="timeout", stderr_tail=stderr[-500:])
    _append_step_log(log_path, attempt, attempts, command, proc.stdout, proc.stderr)
    if proc.returncode != 0:
        return ExecutionResult(status="fail", exit_code=proc.returncode, error="command failed", stderr_tail=proc.stderr[-500:])
    return ExecutionResult(status="pass", exit_code=0)


def _execute_remote_step(
    recipe: Recipe,
    context: dict[str, Any],
    conn: SSHConnection,
    command_template: str,
    timeout: int,
    log_path: Path,
    attempt: int,
    attempts: int,
) -> ExecutionResult:
    command = render_template(command_template, context)
    remote_command = _remote_shell_command(recipe, context, command)
    ssh_args, env = _ssh_args(conn)
    try:
        proc = subprocess.run(
            [*ssh_args, _remote_host(conn), "bash", "-lc", shlex.quote(remote_command)],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stderr = _timeout_text(exc.stderr)
        stdout = _timeout_text(exc.stdout)
        _append_step_log(log_path, attempt, attempts, command, stdout, stderr)
        return ExecutionResult(status="fail", exit_code=124, error="timeout", stderr_tail=stderr[-500:])
    _append_step_log(log_path, attempt, attempts, command, proc.stdout, proc.stderr)
    if proc.returncode != 0:
        return ExecutionResult(status="fail", exit_code=proc.returncode, error="command failed", stderr_tail=proc.stderr[-500:])
    return ExecutionResult(status="pass", exit_code=0)


def _execute_scp_step(
    root: Path,
    context: dict[str, Any],
    conn: SSHConnection | None,
    step: dict[str, Any],
    log_path: Path,
    attempt: int,
    attempts: int,
) -> ExecutionResult:
    if conn is None:
        error = "scp step requires remote recipe"
        _append_step_log(log_path, attempt, attempts, "", "", error)
        return ExecutionResult(status="fail", exit_code=2, error=error, stderr_tail=error)
    src = step.get("src") or step.get("source") or step.get("local_path")
    dst = step.get("dst") or step.get("dest") or step.get("destination") or step.get("remote_path")
    if not isinstance(src, str) or not isinstance(dst, str):
        error = "scp step requires src and dst"
        _append_step_log(log_path, attempt, attempts, "", "", error)
        return ExecutionResult(status="fail", exit_code=2, error=error, stderr_tail=error)
    rendered_src = render_template(src, context)
    rendered_dst = render_template(dst, context)
    direction = step.get("direction") if isinstance(step.get("direction"), str) else None
    direction = direction or ("pull" if step.get("pull") else "push")
    try:
        if direction == "pull":
            local_path = _local_transfer_path(root, rendered_dst)
            _scp_pull(conn, rendered_src, local_path)
            summary = f"pulled {rendered_src} -> {local_path}"
        else:
            local_path = _local_transfer_path(root, rendered_src)
            _scp_push(conn, local_path, rendered_dst)
            summary = f"pushed {local_path} -> {rendered_dst}"
    except RuntimeError as exc:
        _append_step_log(log_path, attempt, attempts, f"scp {direction}", "", str(exc))
        return ExecutionResult(status="fail", exit_code=1, error=str(exc), stderr_tail=str(exc)[-500:])
    _append_step_log(log_path, attempt, attempts, f"scp {direction}", summary + "\n", "")
    return ExecutionResult(status="pass", exit_code=0)


def _resolve_connection(config: dict[str, Any], target_name: str) -> SSHConnection:
    return resolve_connection(config, target_name)


def _scp_pull(conn: SSHConnection, remote_path: str, local_path: Path) -> None:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    args, env = _scp_args(conn)
    proc = subprocess.run(
        [*args, f"{_remote_host(conn)}:{remote_path}", str(local_path)],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "scp pull failed")


def _scp_push(conn: SSHConnection, local_path: Path, remote_path: str) -> None:
    args, env = _scp_args(conn)
    proc = subprocess.run(
        [*args, str(local_path), f"{_remote_host(conn)}:{remote_path}"],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "scp push failed")


def _pull_declared_artifacts(
    root: Path,
    recipe: Recipe,
    context: dict[str, Any],
    conn: SSHConnection,
    artifact_dir: Path,
) -> list[str]:
    artifacts: list[str] = []
    for produced in recipe.produces:
        if not isinstance(produced, dict) or not produced.get("copy_to_local"):
            continue
        remote = produced.get("artifact")
        if not isinstance(remote, str):
            continue
        remote_path = render_template(remote, context)
        local_spec = produced.get("local_path")
        if isinstance(local_spec, str) and local_spec:
            local_path = _local_transfer_path(root, render_template(local_spec, context))
        else:
            local_path = artifact_dir / Path(remote_path).name
        _scp_pull(conn, remote_path, local_path)
        artifacts.append(_artifact_text(root, local_path))
    return artifacts


def _run_local_command(command: str, cwd: Path, env: dict[str, str], timeout: int) -> subprocess.CompletedProcess[str]:
    bash = _bash_executable()
    if bash is not None:
        return subprocess.run(
            [bash, "-lc", command],
            cwd=cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


def _bash_executable() -> str | None:
    if Path("/bin/bash").exists():
        return "/bin/bash"
    return shutil.which("bash")


def _local_cwd(root: Path, recipe: Recipe, context: dict[str, Any]) -> Path:
    cwd_text = render_template(recipe.working_dir, context) if recipe.working_dir else "."
    return (root / cwd_text).resolve() if not Path(cwd_text).is_absolute() else Path(cwd_text)


def _local_env(recipe: Recipe, context: dict[str, Any]) -> dict[str, str]:
    env = os.environ.copy()
    rendered_env = render_value(recipe.env, context)
    env.update({str(key): str(value) for key, value in rendered_env.items()})
    return env


def _remote_shell_command(recipe: Recipe, context: dict[str, Any], command: str) -> str:
    lines: list[str] = []
    if recipe.working_dir:
        lines.append(f"cd {shlex.quote(render_template(recipe.working_dir, context))}")
    rendered_env = render_value(recipe.env, context)
    for key, value in rendered_env.items():
        lines.append(f"export {str(key)}={shlex.quote(str(value))}")
    lines.append(command)
    return "\n".join(lines)


def _ssh_args(conn: SSHConnection) -> tuple[list[str], dict[str, str]]:
    env = os.environ.copy()
    args = _auth_prefix(conn, env)
    args.extend(["ssh", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=no", "-p", str(conn.port)])
    if conn.auth_mode == "key" and conn.key_path:
        args.extend(["-i", conn.key_path])
    return args, env


def _scp_args(conn: SSHConnection) -> tuple[list[str], dict[str, str]]:
    env = os.environ.copy()
    args = _auth_prefix(conn, env)
    args.extend(["scp", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=no", "-P", str(conn.port)])
    if conn.auth_mode == "key" and conn.key_path:
        args.extend(["-i", conn.key_path])
    return args, env


def _auth_prefix(conn: SSHConnection, env: dict[str, str]) -> list[str]:
    if conn.auth_mode == "password" and conn.password_env:
        if conn.password_env in os.environ:
            env["SSHPASS"] = os.environ[conn.password_env]
        return ["sshpass", "-e"]
    return []


def _remote_host(conn: SSHConnection) -> str:
    return f"{conn.user}@{conn.host}"


def _write_stream_logs(artifact_dir: Path, stdout: str, stderr: str) -> None:
    (artifact_dir / "stdout.log").write_text(stdout, encoding="utf-8")
    (artifact_dir / "stderr.log").write_text(stderr, encoding="utf-8")


def _append_step_log(log_path: Path, attempt: int, attempts: int, command: str, stdout: str, stderr: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"attempt {attempt}/{attempts}\n")
        if command:
            handle.write("$ " + command.rstrip() + "\n")
        if stdout:
            handle.write("[stdout]\n" + stdout)
            if not stdout.endswith("\n"):
                handle.write("\n")
        if stderr:
            handle.write("[stderr]\n" + stderr)
            if not stderr.endswith("\n"):
                handle.write("\n")


def _base_artifacts(root: Path, artifact_dir: Path) -> list[str]:
    artifacts: list[str] = []
    for name in ("stdout.log", "stderr.log"):
        path = artifact_dir / name
        if path.exists():
            artifacts.append(_artifact_text(root, path))
    return artifacts


def _existing_produced_artifacts(root: Path, recipe: Recipe, context: dict[str, Any]) -> list[str]:
    artifacts: list[str] = []
    for produced in recipe.produces:
        artifact = produced.get("artifact") if isinstance(produced, dict) else None
        if isinstance(artifact, str):
            rendered = render_template(artifact, context)
            path = (root / rendered).resolve() if not Path(rendered).is_absolute() else Path(rendered)
            if path.exists():
                artifacts.append(_artifact_text(root, path))
    return artifacts


def _artifact_text(root: Path, path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(root))
    except ValueError:
        return str(resolved)


def _local_transfer_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (root / path).resolve()


def _safe_step_name(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("._")
    return safe or "step"


def _timeout_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
