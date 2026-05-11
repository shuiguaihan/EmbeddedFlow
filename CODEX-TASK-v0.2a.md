# Codex Task: EmbeddedFlow v0.2a — SSH Remote Execution

## Task

Execute the v0.2a portion of `.omx/plans/evidence-dag-v0.2-implementation-plan.md`. Implement SSH remote shell execution, SCP artifact transfer, multi-step recipe support, and run history commands for the EmbeddedFlow Evidence-DAG CLI.

## Context

EmbeddedFlow is a project-local Evidence-DAG CLI (`ef`) for embedded product software workflows. v0.1 is complete with local shell + manual recipe types. v0.2a extends the shell executor to support remote SSH execution.

Read these files first for full context:
- `.omx/plans/evidence-dag-v0.2-implementation-plan.md` — detailed implementation plan
- `DESIGN-evidence-dag-zh.md` — full architecture design (Chinese)
- `src/embeddedflow/cli.py` — CLI entry point
- `src/embeddedflow/executors/shell.py` — current local-only shell executor
- `src/embeddedflow/models.py` — data models
- `src/embeddedflow/config.py` — config loading
- `src/embeddedflow/loaders.py` — YAML loaders
- `src/embeddedflow/status.py` — evidence validity checker
- `tests/test_cli_integration.py` — existing integration tests (must not break)
- `tests/test_core.py` — existing unit tests (must not break)

## Deliverables

### 1. SSH Remote Shell Executor

Modify `src/embeddedflow/executors/shell.py`:

- When `recipe.remote is True`, route to `_execute_remote()` instead of raising `CliError`
- `_execute_remote()` uses `subprocess.run(["ssh", ...])` — no paramiko, no new dependencies
- SSH connection params come from `config["local_env"]["targets"][recipe.target]`
- Implement `_resolve_connection()` that returns an `SSHConnection` dataclass
- SSH uses `-o ConnectTimeout=10 -o StrictHostKeyChecking=no` and recipe timeout
- Capture stdout/stderr to local artifact dir just like local execution
- Password auth via `sshpass` if `auth_mode == "password"` and `password_env` is set; key auth via `-i key_path`

### 2. SSHConnection Model

Add to `src/embeddedflow/models.py`:

```python
@dataclass(slots=True)
class SSHConnection:
    host: str
    port: int = 22
    user: str = "root"
    auth_mode: str = "password"
    password_env: str | None = None
    key_path: str | None = None
```

### 3. Multi-Step Recipe Support

Add `steps` field to `Recipe` model in `models.py`:
```python
steps: list[dict[str, Any]] = field(default_factory=list)
```

Update `loaders.py` to parse `steps` from recipe YAML.

Implement `_execute_steps()` in `shell.py`:
- Execute each step sequentially
- Each step has: `name`, `command`, optional `ignore_failure`, optional `timeout`, optional `retry`
- `type: scp` steps call `_scp_pull()` or `_scp_push()`
- Each step logs to `artifact_dir/step_{name}.log`
- Overall result is pass only if all non-ignored steps pass
- If recipe has `steps`, use `_execute_steps()`; if it has `command`, use single-command execution

### 4. SCP Artifact Transfer

Implement in `shell.py`:
- `_scp_pull(conn, remote_path, local_path)` using `subprocess.run(["scp", ...])`
- `_scp_push(conn, local_path, remote_path)` using `subprocess.run(["scp", ...])`
- After remote recipe execution, check `produces` for `copy_to_local: true` entries and pull them

### 5. Config Resolution

Modify `src/embeddedflow/config.py`:
- Add `resolve_connection(config, target_name) -> SSHConnection` function
- Reads from `config["local_env"]["targets"][target_name]`
- Raises `ConfigError` if target not found in local_env

### 6. CLI Updates

Modify `src/embeddedflow/cli.py`:
- Remove the `CliError("remote shell recipes are not implemented in this v0.1 slice")` line in `_execute_recipe()`
- Instead, pass config to `execute_shell()`: `return execute_shell(root, req.id, recipe, config)`
- Load config in `_execute_recipe()` from `load_project_config(root)`
- Add `run` subcommand with `list` and `show` sub-subcommands
- Add `profile show` sub-subcommand

`ef run list`:
- Scan evidence.jsonl, group events by `run` field
- Display: run_id, first event timestamp, req_id, node count, pass/fail summary
- Support `--limit N` argument (default 20)

`ef run show <run-id>`:
- Filter evidence.jsonl by run_id
- Display all events for that run in chronological order

`ef profile show <profile-id>`:
- Load and display profile.yaml + local.env.yaml (if exists) merged config

### 7. Update execute_shell Signature

Current: `execute_shell(root, req_id, recipe)`
New: `execute_shell(root, req_id, recipe, config=None)`

The `config` parameter is optional for backward compatibility. When `None`, load config from root. When `remote: true`, config is required (has connection info).

### 8. Tests

**Critical: All 13 existing tests must continue to pass.**

Update `tests/test_cli_integration.py`:

a) **Update remote test** (`test_remote_shell_recipe_is_rejected_without_pass_evidence`):
- Rename to `test_remote_shell_recipe_requires_connection_config`
- Remote recipe without `local.env.yaml` target config should fail with clear error (e.g., "no connection config for target: vm")
- No pass evidence should be recorded

b) **Add multi-step recipe test**:
- Create a recipe with `steps: [{name: step1, command: "echo hello"}, {name: step2, command: "echo world"}]`
- Run `ef satisfy` and verify both steps execute and evidence is recorded

c) **Add run list/show test**:
- After `ef satisfy`, run `ef run list` and verify output contains the run ID
- Run `ef run show <run-id>` and verify it shows the events

d) **Add connection resolution unit test** in `tests/test_core.py`:
- Test `resolve_connection()` with valid config
- Test `resolve_connection()` with missing target raises `ConfigError`

### 9. Documentation

Update `README.md`:
- Change SSH remote shell from "Deferred" to "Supported"
- Change SCP/artifact transfer from "Deferred" to "Supported"
- Add multi-step recipes as "Supported"
- Add run history as "Supported"

Update version in `pyproject.toml` to `0.2.0`.

## Constraints

- **No new dependencies** — only PyYAML (already present). Use subprocess for SSH/SCP.
- **No SSH in sandbox** — tests for remote execution must mock subprocess or use a local fallback. Do NOT attempt actual SSH connections in tests.
- **Backward compat** — all existing tests pass, simulated EXM-K example works unchanged
- **Python 3.10+** — use modern type annotations
- **Immutable patterns** — prefer frozen dataclasses, avoid mutation

## Verification

After all changes, run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m compileall -q src tests
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m embeddedflow.cli --help
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m embeddedflow.cli run --help
cd examples/exm-k && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../../src python3 -m embeddedflow.cli dag REQ-EXM-FUEL-GAUGE-001 --format json
cd examples/exm-k && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../../src python3 -m embeddedflow.cli satisfy REQ-EXM-FUEL-GAUGE-001 --dry-run
```

All must pass with zero errors.
