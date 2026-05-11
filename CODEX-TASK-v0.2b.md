# Codex Task: EmbeddedFlow v0.2b — Agent Tasks + Python Plugins + Parallel Jobs

## Task

Execute the v0.2b portion of `.omx/plans/evidence-dag-v0.2-implementation-plan.md`. Implement the `agent_task` recipe executor, `python` plugin executor, `--jobs N` parallel execution, test design schema validation, and `ef evidence compact` command.

## Context

EmbeddedFlow is a project-local Evidence-DAG CLI (`ef`) for embedded product software workflows. v0.1 (local shell + manual) and v0.2a (SSH remote + SCP + multi-step + run history) are complete with 16 passing tests.

Read these files first for full context:
- `.omx/plans/evidence-dag-v0.2-implementation-plan.md` — v0.2b architecture and deliverables
- `DESIGN-evidence-dag.md` — full architecture design (section 7.7 Agent Task Recipe, section 11.1 test_design_v1 schema)
- `DESIGN-evidence-dag-zh.md` — Chinese version of above
- `src/embeddedflow/cli.py` — CLI entry point (see `_execute_recipe()` at line 157 and `cmd_satisfy()` at line 166)
- `src/embeddedflow/executors/shell.py` — shell executor (reference for new executors)
- `src/embeddedflow/executors/base.py` — `ExecutionResult` dataclass
- `src/embeddedflow/executors/__init__.py` — executor registry
- `src/embeddedflow/models.py` — data models (Recipe, EvidenceEvent, Graph)
- `src/embeddedflow/evidence.py` — EvidenceStore with append-only JSONL and file locking
- `src/embeddedflow/config.py` — config loading
- `src/embeddedflow/loaders.py` — YAML recipe/requirement loaders
- `src/embeddedflow/context.py` — `build_context()` for AI agent context API
- `src/embeddedflow/template.py` — `render_template()` for variable expansion
- `tests/test_cli_integration.py` — integration tests (16 tests, must not break)
- `tests/test_core.py` — unit tests (must not break)

## Deliverables

### 1. Agent Task Executor

New file: `src/embeddedflow/executors/agent_task.py`

The `agent_task` executor prepares context and instructions for an external AI agent. It does NOT call any AI API.

```python
def execute_agent_task(root: Path, req_id: str, recipe: Recipe, config: dict) -> ExecutionResult:
    """
    1. Read agent_task config from recipe.raw["agent_task"]
    2. Render context_query template using render_template()
    3. Execute the context query command via subprocess to get context JSON
    4. Render instructions template with template variables
    5. Write instructions + context to artifact directory:
       - {artifact_dir}/instructions.md
       - {artifact_dir}/context.json
    6. If output_path is specified, ensure parent directory exists
    7. Return ExecutionResult(status="pass") — actual AI work happens externally
    8. The AI agent reads instructions, does its work, then calls:
       ef recipe complete <recipe-id> <req-id> --artifact <output-path>
    """
```

Recipe YAML fields to support (from `recipe.raw["agent_task"]`):
- `context_query`: template string for ef context command
- `instructions`: template string with instructions for the AI agent
- `output_schema`: optional schema name (e.g., `test_design_v1`)
- `output_path`: template string for where to write output
- `source_verification`: `required` | `optional` | `none`

Implementation details:
- Use `render_template()` from `template.py` to expand `{{profile.*}}`, `{{req.*}}`, etc.
- Use `subprocess.run()` to execute the context query and capture stdout as JSON
- Write `instructions.md` and `context.json` to `{root}/.ef/artifacts/{req_id}/{recipe.id}/`
- If context query fails, return `ExecutionResult(status="fail", error=...)`
- Timeout: use `recipe.timeout` for subprocess calls
- The executor itself always returns `status="pass"` if setup succeeds — the agent task is asynchronous

### 2. `ef recipe complete` Command Enhancement

Modify `src/embeddedflow/cli.py`:

Currently `ef recipe complete` records evidence. Enhance it for agent_task recipes:
- Accept `--artifact <path>` argument for the output file produced by the AI agent
- If the recipe has `output_schema` in `agent_task` config, validate the artifact against that schema (see Deliverable 4)
- If validation fails, record `status="fail"` with error details
- If validation passes, copy artifact to `{root}/.ef/artifacts/{req_id}/{recipe_id}/` and record `status="pass"`

### 3. Python Plugin Executor

New file: `src/embeddedflow/executors/python_plugin.py`

```python
def execute_python(root: Path, req_id: str, recipe: Recipe, config: dict) -> ExecutionResult:
    """
    Load and execute a Python plugin from .ef/plugins/.

    1. Read plugin path from recipe.raw.get("plugin", recipe.id)
    2. Resolve full path: {root}/.ef/plugins/{plugin}.py
    3. Validate the plugin file exists
    4. Use importlib to dynamically load the module:
       - import importlib.util
       - spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
       - module = importlib.util.module_from_spec(spec)
       - spec.loader.exec_module(module)
    5. Validate the module has a callable 'run' function
    6. Call module.run(root, req_id, recipe, config) -> dict
       Expected return: {"status": "pass"|"fail", "artifacts": [...], "error": "..."}
    7. Convert return dict to ExecutionResult
    8. Handle exceptions: catch any Exception from plugin execution,
       return ExecutionResult(status="fail", error=str(e))
    """
```

Plugin interface contract (document in README):
```python
# .ef/plugins/my_plugin.py
def run(root: Path, req_id: str, recipe: Recipe, config: dict) -> dict:
    """
    Returns: {"status": "pass"|"fail", "artifacts": [...], "error": "..."}
    """
```

Implementation details:
- Plugin directory: `{root}/.ef/plugins/`
- Plugin name from `recipe.raw.get("plugin")` or falls back to `recipe.id`
- Use `importlib.util` — no `sys.path` modification, load by file path
- Wrap execution in try/except to catch plugin errors gracefully
- Enforce timeout: run plugin in a thread with `threading.Timer` or `concurrent.futures.ThreadPoolExecutor` with timeout
- Pass a copy of config (not mutable reference) to the plugin

### 4. Test Design Schema Validation

New file: `src/embeddedflow/schema.py`

Implement a lightweight YAML schema validator for `test_design_v1`:

```python
def validate_test_design_v1(data: dict) -> list[str]:
    """
    Validate a test_design_v1 document against required structure.
    Returns list of error strings (empty = valid).

    Required top-level keys:
    - schema: must be "test_design_v1"
    - requirement: non-empty string
    - stimulus: dict with at least 'type' key
    - observations: non-empty list, each with 'id' and 'type'
    - pass_criteria: non-empty list, each with 'id' and 'type'
    - automation_plan: dict with 'automated' and 'manual' lists

    Optional top-level keys:
    - review, produced_by, produced_at, known_gaps, risks
    """

def validate_schema(schema_name: str, data: dict) -> list[str]:
    """
    Route to appropriate validator by schema name.
    Currently supports: test_design_v1
    Returns list of error strings (empty = valid).
    Raises ValueError for unknown schema names.
    """
```

Implementation details:
- Pure Python validation, no external schema library
- Check required keys exist and have correct types
- Check nested structure minimally (not deep validation of every field)
- Return human-readable error messages
- Designed to be extensible for future schemas

### 5. `--jobs N` Parallel Execution

Modify `src/embeddedflow/cli.py` `cmd_satisfy()`:

```python
def cmd_satisfy(args: argparse.Namespace) -> int:
    ...
    if args.jobs and args.jobs > 1:
        # Execute same-level nodes concurrently
        for level in topological_levels(graph):
            runnable = [node for node in level if _should_run(node, ...)]
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
                futures = {
                    pool.submit(_execute_and_record, root, req, graph, store, run_id, node): node
                    for node in runnable
                }
                for future in concurrent.futures.as_completed(futures):
                    node = futures[future]
                    result = future.result()
                    if result.status != "pass" and not args.continue_on_error:
                        # Cancel remaining futures
                        ...
    else:
        # Current sequential execution (unchanged)
        ...
```

Implementation details:
- Add `--jobs N` argument to `satisfy` subparser, default=1
- Use `concurrent.futures.ThreadPoolExecutor` from standard library
- Execute nodes within the same topological level in parallel
- Different levels still execute sequentially (dependencies must be met)
- Evidence recording already has file locking (fcntl in `evidence.py`), safe for concurrent appends
- Extract `_execute_and_record()` helper from the current inline logic in `cmd_satisfy()`
- Print output remains ordered: collect results, then print in node order
- If any node fails and `--continue-on-error` is not set, cancel remaining futures in the current level
- `--jobs 1` must behave identically to current sequential execution (backward compat)

### 6. `ef evidence compact` Command

Modify `src/embeddedflow/evidence.py` — add `compact()` method:

```python
def compact(self) -> tuple[int, int]:
    """
    Compact the evidence JSONL by keeping only the latest cycle per node.

    Algorithm:
    1. Read all events
    2. For each (req, node) pair, find the latest 'produced' or 'failed' event
    3. Keep: the latest produced/failed event + any 'reviewed' events after it
    4. Keep: any 'invalidated' events (they mark state transitions)
    5. Discard: older produced/failed events that are superseded
    6. Write surviving events back to evidence.jsonl (atomic: write to .tmp, then rename)

    Returns: (original_count, surviving_count)
    """
```

Modify `src/embeddedflow/cli.py` — add `evidence compact` subcommand:

```python
def cmd_evidence_compact(args: argparse.Namespace) -> int:
    root = project_root()
    store = EvidenceStore(evidence_path(root))
    if args.dry_run:
        original, surviving = store.compact(dry_run=True)
        print(f"Would compact {original} events to {surviving} ({original - surviving} removed)")
        return 0
    original, surviving = store.compact()
    print(f"Compacted {original} events to {surviving} ({original - surviving} removed)")
    return 0
```

Arguments:
- `--dry-run`: show what would be compacted without modifying the file

### 7. CLI Routing Updates

Modify `_execute_recipe()` in `src/embeddedflow/cli.py`:

```python
def _execute_recipe(root: Path, req: Requirement, recipe: Recipe):
    if recipe.type == "shell":
        config = load_project_config(root)
        return execute_shell(root, req.id, recipe, config)
    if recipe.type == "manual":
        return execute_manual(root, req.id, recipe)
    if recipe.type == "agent_task":
        config = load_project_config(root)
        return execute_agent_task(root, req.id, recipe, config)
    if recipe.type == "python":
        config = load_project_config(root)
        return execute_python(root, req.id, recipe, config)
    raise CliError(f"unsupported recipe type: {recipe.type}")
```

Add imports at top of cli.py:
```python
from .executors.agent_task import execute_agent_task
from .executors.python_plugin import execute_python
```

Update `executors/__init__.py`:
```python
from .base import ExecutionResult
from .agent_task import execute_agent_task
from .python_plugin import execute_python

__all__ = ["ExecutionResult", "execute_agent_task", "execute_python"]
```

### 8. Version and Documentation

- Bump version in `pyproject.toml` to `0.3.0`
- Update `README.md` support matrix:
  - `agent_task` recipe type: "Supported"
  - `python` plugin recipe type: "Supported"
  - Parallel execution (`--jobs N`): "Supported"
  - Test design schema validation: "Supported"
  - Evidence compaction: "Supported"
- Add brief plugin interface documentation in README

### 9. Tests

**Critical: All 16 existing tests must continue to pass.**

#### New test file: `tests/test_agent_task.py`

a) **Test agent_task executor setup**:
- Create a recipe with `type: agent_task` and `agent_task` config
- Mock subprocess for context query
- Verify instructions.md and context.json are written to artifact dir
- Verify ExecutionResult status is "pass"

b) **Test agent_task with missing context query**:
- Recipe with no `context_query` in agent_task config
- Should return ExecutionResult(status="fail") with error

c) **Test agent_task template rendering**:
- Verify `{{req.id}}`, `{{profile.*}}` are expanded in instructions

#### New test file: `tests/test_python_plugin.py`

a) **Test python plugin executor with valid plugin**:
- Create a temporary `.ef/plugins/test_plugin.py` that returns `{"status": "pass", "artifacts": []}`
- Run `execute_python()` and verify pass result

b) **Test python plugin with missing plugin file**:
- Recipe references non-existent plugin
- Should return fail with "plugin not found" error

c) **Test python plugin with exception**:
- Plugin that raises RuntimeError
- Should return fail with error message, not crash

d) **Test python plugin with invalid return**:
- Plugin returns something other than a dict
- Should return fail with error

#### New test file: `tests/test_parallel.py`

a) **Test parallel satisfy with --jobs 2**:
- Create a requirement with two independent evidence nodes at the same level
- Run `ef satisfy --jobs 2`
- Verify both nodes produce evidence
- Verify evidence is recorded correctly

b) **Test --jobs 1 is identical to sequential**:
- Same scenario as above with `--jobs 1`
- Verify result matches sequential behavior exactly

c) **Test parallel with failure and --continue-on-error**:
- One node fails, another succeeds
- Without `--continue-on-error`: execution stops
- With `--continue-on-error`: both are attempted

#### New test file: `tests/test_schema.py`

a) **Test valid test_design_v1 document**:
- Full valid document from DESIGN-evidence-dag.md section 11.1
- `validate_test_design_v1()` returns empty list

b) **Test missing required keys**:
- Document without `stimulus` key
- Returns error list with "missing required key: stimulus"

c) **Test invalid types**:
- `observations` is a string instead of list
- Returns appropriate error

d) **Test unknown schema name**:
- `validate_schema("unknown_v1", {})` raises ValueError

#### Add to `tests/test_cli_integration.py`:

a) **Test evidence compact**:
- Seed evidence.jsonl with multiple events for same node
- Run `ef evidence compact`
- Verify old events are removed, latest cycle preserved

b) **Test evidence compact --dry-run**:
- Verify file is unchanged after dry-run

## File Change Summary

| File | Action | Description |
|------|--------|-------------|
| `src/embeddedflow/executors/agent_task.py` | **New** | Agent task executor |
| `src/embeddedflow/executors/python_plugin.py` | **New** | Python plugin executor |
| `src/embeddedflow/schema.py` | **New** | test_design_v1 schema validation |
| `src/embeddedflow/executors/__init__.py` | Modify | Register new executors |
| `src/embeddedflow/cli.py` | Modify | Route agent_task/python types, add --jobs, add evidence compact, enhance recipe complete |
| `src/embeddedflow/evidence.py` | Modify | Add `compact()` method |
| `src/embeddedflow/models.py` | No change | Recipe model already has `raw` dict for type-specific config |
| `tests/test_agent_task.py` | **New** | Agent task executor tests |
| `tests/test_python_plugin.py` | **New** | Python plugin executor tests |
| `tests/test_parallel.py` | **New** | Parallel execution tests |
| `tests/test_schema.py` | **New** | Schema validation tests |
| `tests/test_cli_integration.py` | Modify | Add evidence compact tests |
| `pyproject.toml` | Modify | Bump version to 0.3.0 |
| `README.md` | Modify | Update support matrix, add plugin docs |

## Constraints

- **No new dependencies** — only PyYAML (already present). Use stdlib `importlib`, `concurrent.futures`, `threading`.
- **No AI API calls** — agent_task executor only prepares context/instructions files. The AI work happens externally.
- **No network** — tests cannot make SSH or HTTP connections. Mock subprocess where needed.
- **Backward compat** — all 16 existing tests pass, simulated EXM-K example works unchanged, `--jobs 1` behaves identically to current sequential mode.
- **Python 3.10+** — use modern type annotations (`str | None`, `list[str]`)
- **Immutable patterns** — prefer frozen/slots dataclasses, avoid mutation
- **File safety** — evidence.jsonl writes use file locking (already in place). Compact uses atomic write (tmp + rename).

## Execution Order

```
Phase 1: Foundation (do first, no dependencies between these)
  1. Create src/embeddedflow/schema.py (standalone, no imports from other new files)
  2. Create src/embeddedflow/executors/agent_task.py
  3. Create src/embeddedflow/executors/python_plugin.py

Phase 2: CLI Integration (depends on Phase 1)
  4. Update src/embeddedflow/executors/__init__.py
  5. Update _execute_recipe() routing in cli.py
  6. Add --jobs N to cmd_satisfy() in cli.py
  7. Add compact() to evidence.py
  8. Add ef evidence compact subcommand in cli.py
  9. Enhance ef recipe complete for agent_task validation

Phase 3: Tests (depends on Phase 2)
  10. Create tests/test_schema.py
  11. Create tests/test_agent_task.py
  12. Create tests/test_python_plugin.py
  13. Create tests/test_parallel.py
  14. Update tests/test_cli_integration.py (evidence compact tests)

Phase 4: Docs + Version
  15. Update README.md support matrix
  16. Bump version in pyproject.toml to 0.3.0

Phase 5: Verification
  17. Run full test suite (all existing + new tests)
  18. Run compileall
  19. Run simulated EXM-K backward compat check
  20. Verify new CLI commands (ef evidence compact --help, ef satisfy --jobs --help)
```

## Verification

After all changes, run:

```bash
# All tests pass (existing 16 + new tests)
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v

# Compileall
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m compileall -q src tests

# CLI help shows new options
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m embeddedflow.cli --help
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m embeddedflow.cli satisfy --help  # should show --jobs
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m embeddedflow.cli evidence compact --help

# Simulated EXM-K backward compat
cd examples/exm-k && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../../src python3 -m embeddedflow.cli dag REQ-EXM-FUEL-GAUGE-001 --format json
cd examples/exm-k && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../../src python3 -m embeddedflow.cli satisfy REQ-EXM-FUEL-GAUGE-001 --dry-run

# Demo backward compat
cd examples/demo && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../../src python3 -m embeddedflow.cli satisfy REQ-1 --dry-run
```

All must pass with zero errors.
