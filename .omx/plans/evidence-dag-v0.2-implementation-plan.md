# Evidence-DAG v0.2 Implementation Plan

> Status: Ready for execution. This plan builds on the completed v0.1 local/manual MVP.

## Goal

Extend EmbeddedFlow from a local-only MVP to a production-capable embedded workflow tool that can execute recipes on remote hosts (SSH), transfer artifacts (SCP), run multi-step deployment sequences, and track run history. v0.2 is split into two sub-phases:

- **v0.2a** — SSH remote execution + multi-step recipes + run history (unlocks real EXM-K build/deploy)
- **v0.2b** — `agent_task` recipe type + `python` plugin recipes + `--jobs N` parallel execution

CANSim (`cansim` recipe type) and target automation (`target_automation` recipe type) are deferred to v0.3; they depend on hardware availability and are not required to prove remote Evidence-DAG correctness.

## v0.1 Baseline (Completed)

What exists and must not break:

- `ef init`, `status`, `dag`, `satisfy`, `review`, `context`, `what-next`
- `ef evidence list/show/invalidate`, `ef recipe list/run/complete`, `ef profile list`
- Local `shell` recipes (subprocess), `manual` recipes (review gates)
- Append-only `.ef/evidence.jsonl`, source/recipe hash validity, transitive cascade
- `remote: true` rejection with clear error and no pass evidence
- 13 tests passing (unit + CLI integration + docs boundary)
- Simulated EXM-K reference under `examples/exm-k/`

## v0.2a Scope — SSH Remote Execution

### v0.2a Deliverables

| # | Deliverable | Description |
|---|-------------|-------------|
| 1 | **SSH remote shell executor** | Extend `executors/shell.py` to support `remote: true` recipes via SSH |
| 2 | **SCP artifact transfer** | Pull remote artifacts to local `.ef/artifacts/` after remote recipe execution |
| 3 | **Multi-step recipe support** | Execute `steps` array in recipe YAML sequentially on remote or local host |
| 4 | **`ef run list/show`** | Run history commands reading from evidence.jsonl grouped by run ID |
| 5 | **`ef profile show`** | Display resolved profile config with template variables |
| 6 | **Real EXM-K recipes** | Production `build.yaml` and `deploy.yaml` with `remote: true` and `steps` |
| 7 | **Connection config** | `local.env.yaml` parsing for SSH host/port/user/auth |
| 8 | **Integration tests** | Remote recipe tests (with mock SSH or local fallback) |

### v0.2a Architecture

#### 1. SSH Remote Shell Executor

Modify `src/embeddedflow/executors/shell.py`:

```python
# Current: remote: true raises CliError
# v0.2a: remote: true routes to SSH execution

def execute_shell(root: Path, req_id: str, recipe: Recipe, config: dict) -> ExecutionResult:
    if recipe.remote:
        return _execute_remote(root, req_id, recipe, config)
    return _execute_local(root, req_id, recipe, config)

def _execute_remote(root: Path, req_id: str, recipe: Recipe, config: dict) -> ExecutionResult:
    target = recipe.raw.get("target", "default")
    conn = _resolve_connection(target, config)
    # SSH execution via subprocess: ssh user@host -p port 'command'
    # Timeout via -o ConnectTimeout + recipe.timeout
    # Capture stdout/stderr to local artifact dir
    ...

def _resolve_connection(target: str, config: dict) -> SSHConnection:
    # Read from config["local_env"]["targets"][target]
    # Fields: host, port, user, auth_mode
    ...
```

Key design decisions:
- Use `subprocess.run(["ssh", ...])` — no paramiko dependency, keep dependencies minimal (PyYAML only)
- SSH connection params from `local.env.yaml` `targets` section
- `ConnectTimeout=10` and recipe-level timeout enforced
- Password auth via environment variable reference (`password_env` field), not stored in YAML
- Remote `working_dir` resolved via template variables

#### 2. SCP Artifact Transfer

For recipes with `produces` entries that have `copy_to_local: true`:

```python
def _pull_artifacts(conn: SSHConnection, recipe: Recipe, artifact_dir: Path, config: dict) -> list[str]:
    local_artifacts = []
    for produced in recipe.produces:
        if produced.get("copy_to_local"):
            remote_path = render_template(produced["artifact"], config)
            local_path = artifact_dir / Path(remote_path).name
            _scp_pull(conn, remote_path, local_path)
            local_artifacts.append(str(local_path))
    return local_artifacts

def _scp_pull(conn: SSHConnection, remote_path: str, local_path: Path) -> None:
    # subprocess.run(["scp", "-P", port, "user@host:remote_path", str(local_path)])
    ...
```

#### 3. Multi-Step Recipe Support

New field `steps` in Recipe model. When present, each step is executed sequentially:

```yaml
# .ef/recipes/deploy.yaml
id: deploy
type: shell
target: board
remote: true
depends_on: [build]
steps:
  - name: stop_existing
    command: "killall EXM-K 2>/dev/null || true"
    ignore_failure: true
  - name: copy_binary
    type: scp
    src: "{{artifacts.build.binary}}"
    dst: "{{profile.deploy.deploy_dir}}"
  - name: start_application
    command: "{{profile.deploy.start_command}}"
  - name: health_check
    command: "pgrep EXM-K"
    retry:
      max_attempts: 5
      interval_seconds: 3
    timeout: 30
```

Implementation:
- Add `steps: list[dict]` field to `Recipe` model
- Add `_execute_steps()` function in shell executor
- Each step produces its own log in `artifact_dir/step_{name}.log`
- `ignore_failure: true` continues on nonzero exit
- `retry` support with max_attempts and interval
- `type: scp` step delegates to `_scp_pull` or `_scp_push`
- Overall recipe result is pass only if all non-ignored steps pass

#### 4. `ef run list/show`

```python
# New commands in cli.py

def cmd_run_list(args) -> int:
    # Scan evidence.jsonl, group events by "run" field
    # Display: run_id, timestamp, req_id, node_count, pass/fail summary
    ...

def cmd_run_show(args) -> int:
    # Filter evidence.jsonl by run_id
    # Display all events in chronological order
    ...
```

#### 5. Connection Data Model

New dataclass in `models.py`:

```python
@dataclass(slots=True)
class SSHConnection:
    host: str
    port: int = 22
    user: str = "root"
    auth_mode: str = "password"  # "password" | "key"
    password_env: str | None = None  # env var name holding password
    key_path: str | None = None
```

Resolution: `config["local_env"]["targets"][target_name]` → `SSHConnection`

### v0.2a File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/embeddedflow/models.py` | Modify | Add `SSHConnection` dataclass, add `steps` field to `Recipe` |
| `src/embeddedflow/executors/shell.py` | Modify | Add `_execute_remote()`, `_execute_steps()`, `_scp_pull()`, `_resolve_connection()` |
| `src/embeddedflow/executors/__init__.py` | No change | |
| `src/embeddedflow/cli.py` | Modify | Remove `remote: true` rejection, add `run list/show` subcommands, pass config to executor |
| `src/embeddedflow/config.py` | Modify | Add `resolve_connection()` helper |
| `src/embeddedflow/loaders.py` | Modify | Parse `steps` from recipe YAML |
| `tests/test_core.py` | Modify | Add SSHConnection, steps parsing, run grouping tests |
| `tests/test_cli_integration.py` | Modify | Update remote test: now expects success with mock; add steps test; add run list/show test |
| `examples/exm-k/.ef/recipes/build.yaml` | Keep as-is | Simulated local stays for CI; real remote recipe in separate example or profile |
| `examples/exm-k-real/.ef/` | New | Real EXM-K recipes with `remote: true` (optional, for manual testing) |
| `pyproject.toml` | Modify | Bump version to `0.2.0` |
| `README.md` | Modify | Update support matrix |
| `DESIGN-evidence-dag.md` | Modify | Update v0.2 section |
| `DESIGN-evidence-dag-zh.md` | Modify | Update v0.2 section |

### v0.2a Testing Strategy

Since SSH integration cannot be tested in CI without real hosts:

1. **Unit tests** — Test `_resolve_connection()`, `_execute_steps()` logic with mocked subprocess
2. **Local fallback test** — `remote: true` with `target: local` (special target that runs locally via subprocess, validates the routing logic)
3. **CLI integration** — `ef run list`, `ef run show` with pre-seeded evidence.jsonl
4. **Manual smoke** — Real EXM-K VM build + board deploy (documented procedure, not automated CI)
5. **Preserve v0.1 tests** — All 13 existing tests must continue to pass; update remote rejection test to test routing instead

### v0.2a Verification Checklist

```bash
# All existing tests still pass
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v

# Compileall
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m compileall -q src tests

# CLI help shows new commands
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m embeddedflow.cli run --help

# Simulated EXM-K still works (v0.1 backward compat)
cd examples/exm-k
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../../src python3 -m embeddedflow.cli dag REQ-EXM-FUEL-GAUGE-001 --format json
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../../src python3 -m embeddedflow.cli satisfy REQ-EXM-FUEL-GAUGE-001 --dry-run
```

---

## v0.2b Scope — Agent Tasks + Python Plugins + Parallel Jobs

### v0.2b Deliverables

| # | Deliverable | Description |
|---|-------------|-------------|
| 1 | **`agent_task` recipe type** | Structured AI prompt/response protocol with `ef context` integration |
| 2 | **`python` recipe type** | importlib dynamic loading of `.ef/plugins/*.py` |
| 3 | **`--jobs N` parallel execution** | Concurrent execution of same-level DAG nodes |
| 4 | **Test design schema validation** | `test_design_v1` YAML schema check |
| 5 | **`ef evidence compact`** | Compact old evidence events to control JSONL growth |

### v0.2b Architecture

#### 1. Agent Task Executor

New file `src/embeddedflow/executors/agent_task.py`:

```python
def execute_agent_task(root: Path, req_id: str, recipe: Recipe, config: dict) -> ExecutionResult:
    """
    Agent task recipes produce structured output files.
    The executor:
    1. Renders the context_query template and runs ef context
    2. Renders the instructions template
    3. Writes instructions + context to artifact dir
    4. Returns pass — the actual AI work happens externally
    5. The AI agent calls ef recipe complete when done
    """
    ...
```

The `agent_task` executor does NOT call an AI API — it prepares context and instructions for an external AI agent to consume. The agent then calls `ef recipe complete` to report evidence.

#### 2. Python Plugin Executor

New file `src/embeddedflow/executors/python_plugin.py`:

```python
def execute_python(root: Path, req_id: str, recipe: Recipe, config: dict) -> ExecutionResult:
    """
    Load and execute a Python plugin from .ef/plugins/.
    Plugin must expose: def run(root, req_id, recipe, config) -> dict
    """
    module_path = recipe.raw.get("plugin", recipe.id)
    # importlib.import_module from .ef/plugins/
    ...
```

#### 3. Parallel Execution

Modify `cmd_satisfy` in `cli.py`:

```python
def cmd_satisfy(args):
    ...
    if args.jobs and args.jobs > 1:
        # Execute same-level nodes concurrently using concurrent.futures.ThreadPoolExecutor
        # Each node gets its own thread
        # Evidence recording is serialized (file lock on evidence.jsonl)
        ...
    else:
        # Current sequential execution
        ...
```

Add `--jobs` argument to satisfy parser. Default is 1 (sequential).

### v0.2b File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/embeddedflow/executors/agent_task.py` | New | Agent task executor |
| `src/embeddedflow/executors/python_plugin.py` | New | Python plugin executor |
| `src/embeddedflow/executors/__init__.py` | Modify | Register new executors |
| `src/embeddedflow/cli.py` | Modify | Add `--jobs` to satisfy, route agent_task/python types |
| `src/embeddedflow/evidence.py` | Modify | Add file locking for concurrent appends, add `compact()` method |
| `src/embeddedflow/schema.py` | New | test_design_v1 schema validation |
| `tests/test_agent_task.py` | New | Agent task executor tests |
| `tests/test_python_plugin.py` | New | Python plugin executor tests |
| `tests/test_parallel.py` | New | Parallel execution tests |

---

## Execution Order

```
v0.2a Phase 1: Foundation (must do first)
  1. Add SSHConnection model + steps field to Recipe
  2. Add connection resolution in config.py
  3. Update loaders.py to parse steps
  4. Implement _execute_remote() in shell.py
  5. Implement _execute_steps() in shell.py
  6. Implement _scp_pull() in shell.py

v0.2a Phase 2: CLI + History
  7. Remove remote: true rejection in cli.py
  8. Pass config dict through to executors
  9. Add ef run list/show commands
  10. Add ef profile show command

v0.2a Phase 3: Tests + Docs
  11. Update test_cli_integration.py remote test
  12. Add steps execution test
  13. Add run list/show tests
  14. Add connection resolution unit tests
  15. Update README.md support matrix
  16. Update DESIGN docs v0.2 section
  17. Bump version to 0.2.0

v0.2a Phase 4: Verification
  18. Run full test suite
  19. Run compileall
  20. Run simulated EXM-K backward compat check
  21. Verify new CLI commands

v0.2b (separate execution after v0.2a is verified)
  22-30. Agent task, python plugin, parallel, schema, compact
```

## Risks

| Risk | Mitigation |
|------|-----------|
| SSH not available in Codex sandbox | Use mock subprocess or local-target fallback for tests |
| Steps execution error handling complexity | Start with sequential-only steps, no parallel within a recipe |
| Breaking v0.1 backward compat | Keep simulated EXM-K example unchanged; all 13 existing tests must pass |
| `--jobs` concurrent evidence.jsonl writes | Use fcntl file locking on append (defer to v0.2b) |
| SCP password auth in CI | Use `password_env` to reference env vars; tests use mock |

## Codex Execution Guidance

This plan is designed for Codex execution. Key constraints:

- **No SSH in sandbox**: All remote execution tests must use mocked subprocess or a `target: local` fallback mode
- **No network**: Cannot fetch dependencies; only `PyYAML` (already in deps)
- **File sandbox**: All file operations within the project directory
- **Verification**: Must run the verification checklist before completion
- **Backward compat**: Must not break any existing v0.1 test or behavior
- **Scope**: Execute v0.2a only. v0.2b is a separate future plan.
