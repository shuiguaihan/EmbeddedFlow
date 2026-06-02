# EmbeddedFlow Evidence-DAG Architecture

## 1. Product Definition

EmbeddedFlow is a project-local, AI-agent-first workflow CLI for Linux embedded product software. It helps turn real requirements into traceable target-device evidence through an **Evidence-DAG** (Directed Acyclic Graph) execution model.

The core insight: **requirement completion = all evidence constraints in a DAG are satisfied**. Instead of walking through a linear stage-gate pipeline, EmbeddedFlow treats the workflow as a constraint satisfaction problem over a graph of evidence nodes.

EmbeddedFlow is not a Codex-only workflow. Codex, Claude Code, Gemini CLI, OpenCode, OMX, and other AI coding terminals are runtime entry points only. The stable workflow center is the independent EmbeddedFlow CLI.

The real service users are embedded product software developers: the people responsible for safely and traceably landing real requirements on target devices. The direct operators are AI coding agents.

---

## 2. v0.3 Release Scope

v0.3.0 is an Evidence-DAG workflow prototype release for Linux-based embedded product software workflows.

### v0.3 Truth Boundary

This section supersedes older v0.1/v0.2 roadmap wording in the rest of this document when there is a conflict. v0.3.0 proves the workflow CLI core and evidence protocol; it is not a real target-device automation release.

Supported in v0.3.0:

- project-local workflow state with append-only evidence event logs
- Evidence-DAG execution model with incremental re-execution
- requirement intake with declarative evidence constraints
- source and recipe hash validity with transitive stale detection
- CLI commands including `ef status`, `ef dag`, `ef satisfy`, `ef review`, and `ef context`
- local shell recipes and SSH remote shell recipes
- SCP artifact transfer and multi-step shell recipes
- manual review gates with required rationale
- `agent_task` recipes that prepare instructions/context for external agents and accept completed artifacts through `ef recipe complete`
- `python` plugin recipes loaded from `.ef/plugins/<plugin>.py`
- parallel execution with `ef satisfy --jobs N`
- `test_design_v1` schema validation
- evidence compaction with `ef evidence compact`
- run history with `ef run list` and `ef run show`
- simulated EXM-K-style project integration as a local shell/manual reference smoke

Deferred after v0.3.0:

- RTOS, MCU, bare-metal, HIL, JTAG, flashing, and power-cycle abstractions
- real EXM-K target smoke with VM or board credentials
- `cansim` recipe type and CANSimService lifecycle management
- `target_automation` recipe type and ZMQ bridge
- target-device screenshot/log automation closed loop
- knowledge provider integration
- global hosted workflow service
- automatic knowledge-base generation and maintenance
- default generation of large process documents

---

## 3. Design Principles

- **Evidence-First**: completion is defined by evidence constraints, not by stage progression.
- **DAG over Pipeline**: dependencies are explicit directed edges, not implicit ordering.
- **Incremental Execution**: only re-execute recipes whose evidence is stale or missing (Make-like).
- **Pull over Push**: AI agents pull context on demand, not receive pre-constructed packets.
- **CLI Core First**: the core workflow is a standalone CLI, not a Codex, OMX, or Claude-specific feature.
- **Project Local State**: each product project stores its own workflow data in its own directory.
- **AI Runtime Agnostic**: AI runtime integrations are thin wrappers around the CLI.
- **Content Hash Validity**: evidence validity is determined by content hashes, not timestamps.
- **Append-Only Audit Trail**: all evidence events are immutable; state is derived from the event log.
- **Recipes over Adapters**: simple YAML recipe definitions replace heavy adapter class hierarchies.
- **Source Verification Required**: knowledge and prior conclusions never replace source inspection.
- **Minimal Data Model**: three core concepts (Requirement, Recipe, Evidence) replace complex object hierarchies.
- **Test Design as Hard Dependency**: verify nodes cannot execute until test design is produced AND reviewed.
- **Linux Embedded First**: v0.3 keeps Linux embedded product delivery as the first product context before expanding to other platforms.

---

## 4. Architecture

```text
AI Coding Agent
  Codex / Claude Code / Gemini CLI / OpenCode / OMX
        |
        v
AI Runtime Adapter (thin wrapper)
        |
        v
EmbeddedFlow CLI Core
        |
        +--> DAG Engine
        |      +--> DAG Builder (requirement + recipe → graph)
        |      +--> Topological Sorter (Kahn's algorithm)
        |      +--> Validity Checker (source_hash, recipe_hash, dependency validity)
        |      +--> Invalidation Cascade (transitive stale marking)
        |      +--> Execution Planner (skip valid, execute stale/missing)
        |
        +--> Recipe Executor
        |      +--> ShellExecutor (local subprocess and SSH remote execution)
        |      +--> ManualExecutor (human gate, blocks until review)
        |      +--> CansimExecutor (deferred: HTTP client for CANSimService)
        |      +--> TargetAutomationExecutor (deferred: ZMQ bridge)
        |      +--> AgentTaskExecutor (v0.3: external-agent handoff protocol)
        |      +--> PythonPluginExecutor (v0.3: importlib dynamic load)
        |
        +--> Evidence Store (append-only JSONL event log)
        |
        +--> Context API (pull-based, structured YAML/JSON output)
        |
        +--> Config Loader (ef.yaml, profile.yaml, local.env.yaml)
        |
        +--> Template Engine ({{variable}} expansion in recipes)
        |
        +--> Source Hasher (SHA-256 of watched file contents)
        |
        +--> KnowledgeProvider (deferred: optional card_kb / markdown_index / none)
```

The CLI core owns DAG construction, validity checking, execution planning, evidence recording, and context generation.

AI runtime adapters may:

- call EmbeddedFlow CLI commands
- read context via `ef context`
- report evidence via `ef recipe complete`
- query next actions via `ef what-next`

AI runtime adapters must not:

- become the workflow source of truth
- store canonical evidence state
- hardcode project-specific target behavior
- require a specific AI platform to run the workflow

---

## 5. Core Concepts

EmbeddedFlow has exactly three core concepts. Everything else is derived.

### 5.1 Requirement

A requirement declares **what evidence is needed** for a piece of work to be considered complete. It does not describe how to produce that evidence.

The YAML below is a future target-device EXM-K shape. The checked-in `examples/exm-k` reference remains a simulated local shell/manual smoke, not a real board flow.

```yaml
# .ef/requirements/REQ-EXM-FUEL-GAUGE-001.yaml
id: REQ-EXM-FUEL-GAUGE-001
title: "燃油表 UI 响应 CAN 油量信号变化"
source: "EXM-K/TODO.md#需求-X"
scope: "EXM-K board verify / fuel gauge status"

# What evidence must be satisfied to close this requirement
evidence:
  - test_design
  - build
  - deploy
  - verify.can_stimulus
  - verify.screenshot
  - verify.comparison
  - verify.log
  - human_review.final

# Source files: changes to these invalidate build and downstream evidence
watch:
  - "EXM-K/src/UI/MainPanel/DashBoardFuelLevel.cpp"
  - "EXM-K/src/UI/MainPanel/DashBoardFuelLevel.h"
  - "EXM-K/src/UILogic/communication/CANBus/FuelLevelHandler.cpp"

tags:
  - board-verify
  - fuel-gauge
  - cansim
```

### 5.2 Recipe

A recipe declares **how to produce** a specific evidence node. It specifies dependencies on other evidence nodes, execution method, and what artifacts it produces.

The remote build recipe below uses the v0.3.0 SSH shell shape. Real EXM-K VM credentials and board execution are still outside v0.3.0 automated readiness.

```yaml
# .ef/recipes/build.yaml
id: build
type: shell
description: "Cross-compile EXM-K with qmake for ARM Cortex-A7 on build VM"

depends_on: []

watch:
  - "EXM-K/**/*.cpp"
  - "EXM-K/**/*.h"
  - "EXM-K/**/*.pro"
  - "EXM-K/**/*.qrc"
  - "EXM-K/**/*.ui"

target: vm
remote: true

env:
  STAGING_DIR: "{{local_env.build_env.env_exports.STAGING_DIR}}"

working_dir: "{{local_env.build_env.build_workdir_override}}"

command: |
  {{local_env.build_env.qmake_path}} ../../EXM-K.pro
  make -j4

produces:
  - artifact: "{{profile.build.artifact_path}}"
    type: arm-elf
    label: binary
  - log: build.log
    type: build_log
    capture: stdout+stderr

timeout: 300
```

### 5.3 Evidence

An evidence event records that a recipe was executed, what it produced, and whether it passed. Evidence is stored as an append-only event log.

```jsonl
{"ts":"2026-04-30T10:00:00Z","event":"produced","node":"build","req":"REQ-EXM-FUEL-GAUGE-001","run":"ef-20260430-001","recipe":"build","status":"pass","duration_s":42,"artifacts":["build.log","EXM-K/build/kilo/EXM-K"],"source_hash":"a1b2c3d4e5f6","recipe_hash":"7890abcd"}
```

---

## 6. Evidence-DAG Execution Model

### 6.1 DAG Construction

When `ef satisfy <req-id>` is invoked:

1. **Load requirement**: Parse `.ef/requirements/<req-id>.yaml`, extract `evidence` list
2. **Load recipes**: For each evidence ID, load `.ef/recipes/<id>.yaml`
3. **Build graph**: For each recipe's `depends_on`, add a directed edge `dependency → dependent`
4. **Resolve transitive**: If recipe A depends on recipe B, and B depends on C, include C in the graph even if the requirement doesn't explicitly list it
5. **Validate graph**: Check for cycles (error), missing recipes (error), orphan nodes (warning)

Example: the simulated `REQ-EXM-FUEL-GAUGE-001` reference produces this local/manual DAG:

```text
┌──────────────┐
│ test_design  │ (manual, review: required)
└──────┬───────┘
       v
┌──────────────┐
│    build     │ (local shell)
└──────┬───────┘
       v
┌──────────────┐
│    deploy    │ (local shell)
└──────┬───────┘
       v
┌────────────────────┐
│ human_review.final │ (manual, review: required)
└────────────────────┘
```

Edges (dependencies):
- build depends_on: [test_design]
- deploy depends_on: [build]
- human_review.final depends_on: [deploy]

Future target-device DAGs may add `verify.can_stimulus`, `verify.screenshot`, `verify.comparison`, and `verify.log` once CANSim and target automation land after v0.3.0.

### 6.2 Topological Sort with Parallelism Detection

Uses Kahn's algorithm (BFS-based). Nodes with in-degree 0 at each iteration form a "level" — nodes within a level have no mutual dependencies and can execute in parallel.

```text
Level 0: test_design
Level 1: build
Level 2: deploy
Level 3: human_review.final
```

### 6.3 Validity Check Algorithm

For each evidence node, determine if existing evidence is still valid:

```python
def is_valid(node_id: str, evidence_store: EvidenceStore, recipes: dict, hasher: SourceHasher) -> bool:
    """
    An evidence node is valid if and only if:
    1. It has a 'produced' event with status='pass' that is not superseded by an 'invalidated' event
    2. The source_hash at production time matches the current source hash
    3. The recipe_hash at production time matches the current recipe hash
    4. All nodes in its depends_on list are themselves valid
    """
    latest = evidence_store.latest_event(node_id)

    # No evidence ever produced, or explicitly invalidated
    if latest is None:
        return False
    if latest.event == "invalidated":
        return False
    if latest.event == "failed":
        return False
    if latest.status != "pass":
        return False

    # Check if recipe has review: required and review is not yet recorded
    recipe = recipes[node_id]
    if recipe.review == "required":
        review_event = evidence_store.latest_review(node_id)
        if review_event is None or review_event.status != "accepted":
            return False

    # Check source hash (watched files changed?)
    if recipe.watch:
        current_hash = hasher.compute(recipe.watch)
        if current_hash != latest.source_hash:
            return False

    # Check recipe hash (recipe definition changed?)
    current_recipe_hash = hasher.compute_recipe(recipe)
    if current_recipe_hash != latest.recipe_hash:
        return False

    # Check all dependencies are valid (transitive)
    for dep_id in recipe.depends_on:
        if not is_valid(dep_id, evidence_store, recipes, hasher):
            return False

    return True
```

### 6.4 Invalidation Cascade

When source files change, invalidation propagates transitively:

```text
Source file examples/exm-k/src/fuel_gauge.txt modified
  -> build watches "src/**/*.txt" -> build is STALE
    -> deploy depends_on [build] -> deploy is STALE
      -> human_review.final depends_on [deploy] -> STALE
```

The invalidation is computed lazily (at `ef status` or `ef satisfy` time) by walking the DAG and checking hashes, not eagerly (no file watcher daemon required).

### 6.5 Incremental Execution (Make-like)

`ef satisfy` only executes recipes for nodes that are NOT valid:

```text
$ ef satisfy REQ-EXM-FUEL-GAUGE-001

[skip]  test_design              review accepted
[run]   build                    stale
[run]   deploy                   depends on stale node
[run]   human_review.final       depends on stale node
[wait]  human_review.final       review required: ef review human_review.final REQ-EXM-FUEL-GAUGE-001 --accept --rationale <text>
```

If nothing has changed since last successful run:

```text
$ ef satisfy REQ-EXM-FUEL-GAUGE-001

All evidence up to date. REQ-EXM-FUEL-GAUGE-001 is satisfied.
```

### 6.6 Partial Execution and Resume

If execution is interrupted (network failure, manual abort), the next `ef satisfy` resumes from where it left off — already-produced evidence is still valid (assuming no source changes), so only remaining nodes execute.

### 6.7 Forced Re-execution

```bash
ef satisfy REQ-EXM-FUEL-GAUGE-001 --force build
```

Forces the `build` node to re-execute even if valid. All nodes depending on `build` will also re-execute (their dependency is now stale).

---

## 7. Recipe System

### 7.1 Recipe Types

| Type | Executor | v0.3 status | Description |
|------|----------|-------------|-------------|
| `shell` | local subprocess or SSH remote | Supported | Run local commands or `remote: true` commands through OpenSSH. |
| `manual` | blocks, waits for `ef review` | Supported | Human gate with required rationale when accepting review nodes. |
| `agent_task` | external-agent handoff | Supported | Prepares instructions/context; external agents report artifacts with `ef recipe complete`. |
| `python` | importlib dynamic load | Supported | Complex logic via project-local Python plugins. |
| `cansim` | built-in HTTP client | Deferred | CANSimService stimulus injection. |
| `target_automation` | built-in ZMQ client | Deferred | Board-side UI automation. |

### 7.2 Shell Recipe — Local Execution

```yaml
id: verify.comparison
type: shell
description: "Compare low and high screenshots pixel-by-pixel"
depends_on: [verify.screenshot]

command: |
  python3 scripts/compare_screenshots.py \
    {{artifacts.verify.screenshot.screenshot_fuel_low.png}} \
    {{artifacts.verify.screenshot.screenshot_fuel_high.png}} \
    --output comparison_report.json \
    --threshold 0.05

produces:
  - artifact: comparison_report.json
    type: comparison_result
  - log: comparison.log
    type: comparison_log
    capture: stdout+stderr
```

### 7.3 Shell Recipe - Remote Execution (SSH)

Remote shell execution is supported in v0.3.0. A recipe with `remote: true` runs through OpenSSH using the selected target from `.ef/profiles/<profile>/local.env.yaml`; `copy_to_local: true` artifacts are retrieved with `scp`.

```yaml
id: build
type: shell
description: "Cross-compile EXM-K via qmake on build VM"

depends_on: []

watch:
  - "EXM-K/**/*.cpp"
  - "EXM-K/**/*.h"
  - "EXM-K/**/*.pro"
  - "EXM-K/**/*.qrc"
  - "EXM-K/**/*.ui"
  - "EXM-K/**/*.pri"

# Remote execution on the VM target defined in profile
target: vm
remote: true

env:
  STAGING_DIR: "{{local_env.build_env.env_exports.STAGING_DIR}}"

working_dir: "{{local_env.build_env.build_workdir_override}}"

command: |
  {{local_env.build_env.qmake_path}} ../../EXM-K.pro
  make -j4

produces:
  - artifact: "{{profile.build.artifact_path}}"
    type: arm-elf
    label: binary
    copy_to_local: true
    local_path: ".ef/artifacts/{{req.id}}/build/EXM-K"
  - log: build.log
    type: build_log
    capture: stdout+stderr

timeout: 300
on_failure:
  capture: [stdout, stderr, make_error_log]
```

### 7.4 Shell Recipe - Multi-Step Deploy (SSH/SCP)

Multi-step shell recipes and SCP steps are supported in v0.3.0. The example below shows the intended target-board shape, but `examples/exm-k` still uses a simulated local shell/manual smoke rather than a real board flow.

```yaml
id: deploy
type: shell
description: "Deploy EXM-K binary to target board via SSH"

depends_on: [build]

target: board
remote: true

steps:
  - name: stop_existing
    command: "killall EXM-K 2>/dev/null || true"
    post_wait_seconds: "{{profile.deploy.stop_wait_seconds}}"
    ignore_failure: true

  - name: backup_current
    command: |
      if [ -f {{profile.deploy.deploy_dir}}/EXM-K ]; then
        cp {{profile.deploy.deploy_dir}}/EXM-K {{profile.deploy.deploy_dir}}/EXM-K.bak
      fi
    ignore_failure: true

  - name: copy_binary
    type: scp
    src: "{{artifacts.build.binary}}"
    dst: "{{profile.deploy.copy_targets[0].dst}}"
    mode: "755"

  - name: start_application
    command: "{{profile.deploy.start_command}}"

  - name: health_check
    command: "{{profile.deploy.health_checks | join(' && ')}}"
    retry:
      max_attempts: 8
      interval_seconds: 5
    timeout: "{{profile.deploy.startup_timeout_seconds}}"

produces:
  - log: deploy.log
    type: deploy_log
    capture: all_steps
  - status: health_result
    type: health_check
    fields:
      process_running: bool
      log_file_exists: bool
      startup_time_seconds: float
```

### 7.5 CANSim Recipe (Deferred after v0.3)

```yaml
id: verify.can_stimulus
type: cansim
description: "Inject fuel level CAN signals via CANSimService HTTP API"

depends_on: [deploy, test_design]

cansim:
  host: "{{resolved.cansim.host}}"
  port: "{{resolved.cansim.port}}"
  transport: http
  timeout_seconds: 10

  # Pre-flight checks before stimulus
  pre_checks:
    - endpoint: /health
      expect: {"status": "ok"}
    - endpoint: /channels
      expect_contains: "{{profile.verify.cansim_channel}}"

  # Stimulus actions executed in sequence
  actions:
    - type: signals_set
      label: fuel_low
      source: "{{profile_dir}}/cansim_sequences/fuel_level_low.signals.json"
      settle_ms: 2500
      capture_trigger: true

    - type: signals_set
      label: fuel_high
      source: "{{profile_dir}}/cansim_sequences/fuel_level_high.signals.json"
      settle_ms: 2500
      capture_trigger: true

    - type: sequence_run
      label: full_sweep
      source: "{{profile_dir}}/cansim_sequences/fuel_gauge_sweep.sequence.json"
      wait_for_completion: true

  # Cleanup after stimulus
  post_cleanup:
    - endpoint: /periodic/stop
      method: POST

produces:
  - log: cansim_stimulus.log
    type: stimulus_record
    fields:
      frames_sent: int
      sequences_completed: int
      errors: list
  - artifact: stimulus_results.json
    type: stimulus_evidence
    contains: all_request_response_pairs
```

### 7.6 Target Automation Recipe (Deferred after v0.3)

```yaml
id: verify.screenshot
type: target_automation
description: "Capture board screenshots via TestAutomation ZMQ bridge"

depends_on: [verify.can_stimulus]

target_automation:
  board: "{{profile.targets.board}}"
  command_port: 5661
  reply_port: 7661
  topic: "/BROKER/EXM/TestAutomation/Command"
  reply_topic: "/BROKER/EXM/TestAutomation/Reply"
  timeout_ms: 5000
  ssh_tunnel: true

  actions:
    - cmd: goto_page
      args:
        page_id: main_panel
      expect_reply: true

    - cmd: wait_stable
      args:
        duration_ms: 2000
      expect_reply: false

    - cmd: capture_screenshot
      args:
        label: fuel_current_state
        format: png
      expect_reply: true
      pull_artifact: true
      remote_path: "/tmp/screenshot_*.png"

produces:
  - artifact: "screenshot_*.png"
    type: board_screenshot
    multiple: true
  - log: target_automation.log
    type: automation_log
    fields:
      commands_sent: int
      replies_received: int
      screenshots_captured: int
      errors: list
```

### 7.7 Agent Task Recipe (v0.3 Supported)

```yaml
id: test_design
type: agent_task
description: "AI agent generates test design for requirement verification"

depends_on: []

review: required

agent_task:
  # The context query the agent should use to get inputs
  context_query: "ef context {{req.id}} --need test_design --format json"

  # Instructions for the AI agent
  instructions: |
    You are designing a test plan for requirement {{req.id}}: {{req.title}}.

    Steps:
    1. Read the source files listed in the requirement's watch list
    2. Identify what CAN signals affect this UI element
    3. Define stimulus inputs (CAN frames, signal values, timing)
    4. Define observation points (UI elements, log patterns, screenshots)
    5. Define pass/fail criteria
    6. Define automation vs manual split
    7. Identify known gaps and risks

    Output format: YAML following the test_design_v1 schema.
    Source verification: REQUIRED - verify all assumptions against actual source code.

  # Expected output schema
  output_schema: test_design_v1

  # Where to write the output
  output_path: ".ef/artifacts/{{req.id}}/test_design/test_design.yaml"

  # Source verification policy
  source_verification: required

produces:
  - document: test_design.yaml
    type: test_design
    schema: test_design_v1
    must_contain:
      - stimulus
      - observations
      - pass_criteria
      - automation_plan
```

### 7.8 Manual Recipe (Human Gate)

```yaml
id: human_review.final
type: manual
description: "Final human acceptance of all verification evidence"

depends_on:
  - verify.can_stimulus
  - verify.screenshot
  - verify.comparison
  - verify.log

manual:
  # What to show the reviewer
  prompt: |
    Review evidence for {{req.id}}: {{req.title}}

    Evidence collected:
    - Build: {{artifacts.build.log}} ({{evidence.build.status}})
    - Deploy: {{artifacts.deploy.log}} ({{evidence.deploy.status}})
    - CAN Stimulus: {{artifacts.verify.can_stimulus.log}} ({{evidence.verify.can_stimulus.status}})
    - Screenshots: {{artifacts.verify.screenshot.artifacts}}
    - Comparison: {{artifacts.verify.comparison.artifact}}
    - Board Log: {{artifacts.verify.log.artifact}}

    Decision required: Accept or Reject with rationale.

  # Fields the reviewer must fill
  fields:
    - name: status
      type: enum
      values: [accepted, rejected, conditional]
      required: true
    - name: reviewer
      type: string
      required: true
    - name: rationale
      type: text
      required: true
    - name: conditions
      type: text
      required_if: "status == conditional"
    - name: reviewed_at
      type: timestamp
      auto: true

  # How long to wait for review before timing out
  timeout: null  # no timeout, waits indefinitely

produces:
  - document: acceptance.yaml
    type: human_acceptance
```

### 7.9 Recipe Template Variables

Recipes support Jinja2-style template variables resolved at execution time:

| Variable Namespace | Source | Example |
|---|---|---|
| `{{profile.*}}` | `.ef/profiles/<id>/profile.yaml` | `{{profile.build.artifact_path}}` |
| `{{local_env.*}}` | `.ef/profiles/<id>/local.env.yaml` | `{{local_env.targets.board.host}}` |
| `{{req.*}}` | Current requirement | `{{req.id}}`, `{{req.title}}` |
| `{{resolved.*}}` | Runtime-resolved values | `{{resolved.cansim.host}}` |
| `{{artifacts.<node>.*}}` | Artifacts from dependency nodes | `{{artifacts.build.binary}}` |
| `{{evidence.<node>.*}}` | Evidence status of dependency | `{{evidence.build.status}}` |
| `{{profile_dir}}` | Path to profile directory | `.ef/profiles/exm-k/` |
| `{{project_root}}` | Project root directory | `/mnt/d/Monster_Liu/code/work_code/exm-k-2024` |

---

## 8. Evidence Store

### 8.1 Storage Format

The evidence store is a single file at `.ef/evidence.jsonl`. Each line is one self-contained JSON event. This design supports:

- **Audit trail**: full history of all evidence production and invalidation
- **Replay**: state at any point in time can be reconstructed
- **Append-only safety**: no in-place modification, no data loss
- **Simple implementation**: no database required, just file append

### 8.2 Event Schema

```typescript
interface EvidenceEvent {
  ts: string;           // UTC ISO-8601 timestamp
  event: "produced" | "invalidated" | "reviewed" | "failed" | "skipped";
  node: string;         // evidence node ID (matches recipe ID)
  req: string;          // requirement ID
  run: string;          // run identifier (groups events from one ef satisfy invocation)

  // For 'produced' events:
  recipe?: string;      // recipe that produced it
  status?: "pass" | "fail" | "blocked";
  duration_s?: number;  // execution time
  artifacts?: string[]; // relative paths to produced files
  source_hash?: string; // SHA-256 of watched source files at production time
  recipe_hash?: string; // SHA-256 of recipe definition at production time
  depends?: string[];   // list of "node@hash" dependencies valid at production time

  // For 'invalidated' events:
  reason?: "source_changed" | "recipe_changed" | "dependency_invalidated" | "manual";
  changed_files?: string[];
  old_hash?: string;
  new_hash?: string;

  // For 'reviewed' events:
  reviewer?: string;
  review_status?: "accepted" | "rejected" | "conditional";
  rationale?: string;
  conditions?: string;

  // For 'failed' events:
  error?: string;
  exit_code?: number;
  stderr_tail?: string; // last 500 chars of stderr
}
```

### 8.3 State Derivation

Current state is derived by scanning the event log for each node:

```python
def current_status(node_id: str, req_id: str) -> str:
    """
    Derive current status from event log.
    Returns: 'valid' | 'stale' | 'missing' | 'failed' | 'pending_review' | 'rejected'
    """
    events = filter(evidence_log, node=node_id, req=req_id)
    if not events:
        return 'missing'

    latest = events[-1]  # most recent event for this node+req

    if latest.event == 'invalidated':
        return 'stale'
    if latest.event == 'failed':
        return 'failed'
    if latest.event == 'produced':
        if latest.status == 'pass':
            # Check if review is required but not yet done
            recipe = load_recipe(node_id)
            if recipe.review == 'required':
                review = latest_review_event(node_id, req_id, after=latest.ts)
                if review is None:
                    return 'pending_review'
                if review.review_status == 'rejected':
                    return 'rejected'
            # Check current hashes (lazy invalidation)
            if not hashes_still_match(latest, recipe):
                return 'stale'
            return 'valid'
        return 'failed'
    if latest.event == 'reviewed':
        # A review without a preceding 'produced' shouldn't happen
        return 'missing'

    return 'missing'
```

### 8.4 Source Hash Computation

```python
import hashlib
from pathlib import Path
from fnmatch import fnmatch

def compute_source_hash(watch_patterns: list[str], project_root: Path) -> str:
    """
    Compute SHA-256 hash of all files matching watch patterns.
    Files are sorted by path for deterministic ordering.
    """
    matched_files = []
    for pattern in watch_patterns:
        for path in project_root.rglob("*"):
            if path.is_file() and fnmatch(str(path.relative_to(project_root)), pattern):
                matched_files.append(path)

    matched_files.sort()

    hasher = hashlib.sha256()
    for path in matched_files:
        # Include relative path in hash (rename detection)
        rel = str(path.relative_to(project_root))
        hasher.update(rel.encode())
        hasher.update(path.read_bytes())

    return hasher.hexdigest()[:12]  # 12-char prefix for readability
```

### 8.5 Recipe Hash Computation

```python
def compute_recipe_hash(recipe_path: Path) -> str:
    """
    Compute SHA-256 of recipe YAML content.
    Ignores comments and whitespace normalization for stability.
    """
    import yaml
    content = yaml.safe_load(recipe_path.read_text())
    # Normalize to canonical JSON for hash stability
    canonical = json.dumps(content, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]
```

---

## 9. CLI Command Surface

### 9.1 Command Reference

```bash
# Project initialization
ef init [--profile <id>]
    Create .ef/ directory with default structure.
    If --profile specified, copy starter profile template.

# Core execution
ef satisfy <req-id> [--dry-run] [--force <node>] [--continue-on-error]
    Build DAG for requirement, execute all stale/missing recipes.
    --dry-run: show execution plan without running.
    --force <node>: force re-execution of a specific node.
    --continue-on-error: do not stop on first failure.

v0.3.0 supports `--jobs N` parallel execution for independent DAG nodes in the same level. Additional profile-selection UX remains future work.

# Status and inspection
ef status [<req-id>] [--all]
    Show evidence status for one or all requirements.
    Displays per-node: valid/stale/missing/failed/pending_review.

ef dag <req-id> [--format text|dot|json]
    Visualize the evidence DAG.
    text: ASCII tree with status colors.
    dot: Graphviz DOT language output.
    json: machine-readable graph structure.

ef what-next <req-id>
    Suggest next action based on current DAG state.
    Output: actionable instruction with ef command to run.

# AI agent interface (pull-based context)
ef context <req-id> [--need <node-id>] [--format markdown|json]
    Pull-based context API for AI agents.
    Without --need: full requirement context with DAG status.
    With --need: scoped context for producing specific evidence.

# Evidence management
ef evidence list [<req-id>] [--status valid|stale|failed|all] [--node <id>]
    List evidence events with filters.

ef evidence show <node-id> <req-id>
    Show full details of an evidence node: latest event, artifacts, hashes.

ef evidence invalidate <node-id> <req-id> [--reason <text>]
    Manually invalidate an evidence node. Cascades to dependents.

# Recipe management
ef recipe list [--type shell|manual|cansim|...]
    List all available recipes with type, dependencies, description.

ef recipe run <recipe-id> <req-id> [--force]
    Execute a single recipe directly, outside the DAG satisfy flow.

ef recipe complete <recipe-id> <req-id> --artifact <path> --status pass|fail
    Report completion of an externally-executed recipe (used by AI agents).

# Human review
ef review <node-id> <req-id> --accept|--reject [--reviewer <name>] [--rationale <text>]
    Record human review decision for a manual-gate evidence node.

# Profile management
ef profile list
    List available profiles.

ef profile show <profile-id>
    Show profile configuration with resolved template variables.

# Run history
ef run list [--limit N]
    List recent ef satisfy runs with timestamps and outcomes.

ef run show <run-id>
    Show all evidence events from a specific run.
```

### 9.2 Example Session

This example uses the checked-in simulated EXM-K reference. It is local-only: no SSH, VM, real board, CANSim, target automation, or external agent execution is required.

```bash
# Inspect the simulated requirement
$ ef dag REQ-EXM-FUEL-GAUGE-001 --format json
{
  "levels": [
    ["test_design"],
    ["build"],
    ["deploy"],
    ["human_review.final"]
  ]
}

# Ask what would run without producing evidence
$ ef satisfy REQ-EXM-FUEL-GAUGE-001 --dry-run
[run]   test_design              missing
[run]   build                    missing
[run]   deploy                   missing
[run]   human_review.final       missing

# Execute local/manual recipes
$ ef satisfy REQ-EXM-FUEL-GAUGE-001
[run]   test_design              missing
[wait]  test_design              review required: ef review test_design REQ-EXM-FUEL-GAUGE-001 --accept --rationale <text>
[run]   build                    missing
[run]   deploy                   missing
[run]   human_review.final       missing
[wait]  human_review.final       review required: ef review human_review.final REQ-EXM-FUEL-GAUGE-001 --accept --rationale <text>

# Review-required manual nodes need explicit rationale
$ ef review test_design REQ-EXM-FUEL-GAUGE-001 --accept --reviewer qa --rationale "simulated test design reviewed"
Recorded review for test_design REQ-EXM-FUEL-GAUGE-001: accepted

$ ef review human_review.final REQ-EXM-FUEL-GAUGE-001 --accept --reviewer qa --rationale "simulated build and deploy evidence reviewed"
Recorded review for human_review.final REQ-EXM-FUEL-GAUGE-001: accepted

$ ef status REQ-EXM-FUEL-GAUGE-001 --format json
{
  "satisfied": true,
  "nodes": {
    "test_design": {"status": "valid"},
    "build": {"status": "valid"},
    "deploy": {"status": "valid"},
    "human_review.final": {"status": "valid"}
  }
}
```

Future real-target examples with VM builds, board deploy, CANSim, target automation, screenshots, and board logs remain deferred after v0.3.0. They are not v0.3.0 release acceptance examples.

---

## 10. AI Agent Interface (Pull-Based Context)

### 10.1 Design Philosophy

The fundamental difference from CodexFlow's push-based packet system:

| Aspect | CodexFlow (Push) | EmbeddedFlow (Pull) |
|--------|-----------------|---------------------|
| Context delivery | Pre-constructed packet before agent starts | Agent queries what it needs during execution |
| Information amount | Fixed, may be too much or too little | Exactly what agent requests |
| Staleness | Packet may become stale during execution | Always current at query time |
| Agent autonomy | Agent follows packet instructions | Agent decides what to query |

### 10.2 Full Context Query

```bash
$ ef context REQ-EXM-FUEL-GAUGE-001 --format json
```

Returns current local project data. The context output is JSON or Markdown, and the simulated EXM-K reference contains four local/manual nodes:

```json
{
  "artifacts_root": ".ef/artifacts/REQ-EXM-FUEL-GAUGE-001",
  "dependencies": [],
  "need": null,
  "requirement": {
    "id": "REQ-EXM-FUEL-GAUGE-001",
    "title": "Fuel gauge UI responds to CAN fuel level signal changes",
    "scope": "simulated EXM-K board verification",
    "watch": ["src/**/*.txt"],
    "evidence": ["test_design", "build", "deploy", "human_review.final"]
  },
  "nodes": {
    "test_design": {
      "recipe": {"id": "test_design", "type": "manual", "review": "required"},
      "status": {"status": "missing", "reason": "no produced evidence"}
    },
    "build": {
      "recipe": {"id": "build", "type": "shell", "depends_on": ["test_design"]},
      "status": {"status": "missing", "reason": "no produced evidence"}
    },
    "deploy": {
      "recipe": {"id": "deploy", "type": "shell", "depends_on": ["build"]},
      "status": {"status": "missing", "reason": "no produced evidence"}
    },
    "human_review.final": {
      "recipe": {"id": "human_review.final", "type": "manual", "review": "required"},
      "status": {"status": "missing", "reason": "no produced evidence"}
    }
  }
}
```

The simulated EXM-K context output does not include SSH credentials, board hosts, CANSim endpoints, deployed board paths, or target automation channels.

### 10.3 Scoped Context Query

```bash
$ ef context REQ-EXM-FUEL-GAUGE-001 --need build --format json
```

Returns only the requested node plus its dependencies:

```json
{
  "need": "build",
  "dependencies": ["test_design"],
  "nodes": {
    "test_design": {
      "recipe": {
        "id": "test_design",
        "type": "manual",
        "review": "required",
        "instructions": "Record the CAN stimulus levels, expected UI states, screenshot checks, and log checks before build/deploy evidence is accepted."
      },
      "status": {"status": "missing"}
    },
    "build": {
      "recipe": {
        "id": "build",
        "type": "shell",
        "description": "Simulated EXM-K build artifact",
        "depends_on": ["test_design"],
        "command": "mkdir -p out\ncp src/fuel_gauge.txt out/EXM-K\n",
        "produces": [{"artifact": "out/EXM-K", "type": "simulated-binary", "label": "binary"}]
      },
      "status": {"status": "missing"}
    }
  }
}
```

A scoped context for `verify.can_stimulus` with `type: cansim`, CANSim host/port, board host, or deployed target paths remains deferred after v0.3.0.

### 10.4 Agent Evidence Reporting

After producing evidence externally, agents can report a completed recipe with the implemented v0.3.0 command:

```bash
ef recipe complete test_design REQ-EXM-FUEL-GAUGE-001 \
  --artifact .ef/artifacts/REQ-EXM-FUEL-GAUGE-001/test_design/test_design.yaml \
  --status pass
```

There is no separate `ef evidence record` command. Evidence is recorded by recipe execution, `ef recipe complete`, reviews, and invalidations.

### 10.5 Agent Workflow Pattern

The v0.3.0 local/manual/agent-task interaction pattern is:

```text
1. Agent receives task: "Satisfy REQ-EXM-FUEL-GAUGE-001"
2. Agent calls: ef what-next REQ-EXM-FUEL-GAUGE-001
3. Agent calls: ef context REQ-EXM-FUEL-GAUGE-001 --need build --format json
4. Agent runs: ef satisfy REQ-EXM-FUEL-GAUGE-001 --dry-run
5. Agent runs: ef satisfy REQ-EXM-FUEL-GAUGE-001
6. Human or responsible reviewer accepts required manual nodes with --rationale
7. Agent calls: ef status REQ-EXM-FUEL-GAUGE-001 --format json
```

Agent-task test design generation is supported in v0.3.0. Workflows that combine agent tasks with CANSim stimulus injection, target automation screenshots, and board logs remain deferred after v0.3.0.

---

## 11. Test Design Evidence Structure

This schema is the supported v0.3.0 `test_design_v1` artifact shape. It can be produced by an `agent_task` recipe and validated when the external agent completes the recipe; CANSim-driven target verification remains deferred.

### 11.1 Schema: test_design_v1

The test design is a structured YAML document that may be attached as manual evidence or generated by an `agent_task` recipe. It defines how to verify the requirement when target-device integrations exist.

```yaml
# Full test_design_v1 schema
schema: test_design_v1
requirement: REQ-EXM-FUEL-GAUGE-001
produced_by: agent_task
produced_at: "2026-04-30T09:30:00Z"

# Review tracking
review:
  status: approved        # draft | pending | approved | rejected
  reviewer: "liu"
  reviewed_at: "2026-04-30T09:45:00Z"
  rationale: "Test plan covers all fuel gauge states"

# What CAN signals to inject
stimulus:
  type: cansim_sequence
  provider: CANSimService
  channel: board_can1_rx_via_usb2
  transport: http

  sequences:
    - id: fuel_low
      description: "Set fuel level to 0% (empty)"
      source: ".ef/profiles/exm-k/cansim_sequences/fuel_level_low.signals.json"
      signals:
        - name: iFuelLevel_a
          pgn: "0x00FEF2"
          spn: 96
          value: 0
          unit: "%"
      hold_ms: 2500
      settle_ms: 2500
      expected_ui_state: "fuel ring at minimum, red zone"

    - id: fuel_mid
      description: "Set fuel level to 50% (half)"
      source: ".ef/profiles/exm-k/cansim_sequences/fuel_level_mid.signals.json"
      signals:
        - name: iFuelLevel_a
          value: 50
          unit: "%"
      hold_ms: 2500
      settle_ms: 2500
      expected_ui_state: "fuel ring at middle, yellow zone"

    - id: fuel_high
      description: "Set fuel level to 100% (full)"
      source: ".ef/profiles/exm-k/cansim_sequences/fuel_level_high.signals.json"
      signals:
        - name: iFuelLevel_a
          value: 100
          unit: "%"
      hold_ms: 2500
      settle_ms: 2500
      expected_ui_state: "fuel ring at maximum, green zone"

    - id: fuel_invalid
      description: "Set fuel level to 0xFFFF (invalid/timeout)"
      signals:
        - name: iFuelLevel_a
          value: 0xFFFF
          unit: "raw"
      hold_ms: 2500
      settle_ms: 2500
      expected_ui_state: "fuel display shows '--' or empty"

# What to observe on the target device
observations:
  - id: fuel_ring_visual
    type: visual
    target: "Main panel fuel gauge ring"
    method: board_screenshot
    page_id: main_panel
    roi:
      x: 120
      y: 260
      width: 320
      height: 220
    description: "Ring fill level and color should change with fuel level"

  - id: fuel_icon_color
    type: visual
    target: "Fuel pump icon color"
    method: board_screenshot
    page_id: main_panel
    description: "Icon should be red at low, yellow at mid, green at high"

  - id: fuel_numeric_display
    type: visual
    target: "Fuel percentage number"
    method: board_screenshot
    page_id: main_panel
    description: "Should show 0%, 50%, 100%, or '--' for invalid"

  - id: board_log_check
    type: log
    source: "/userdata/media/EXM.log"
    method: scp_pull
    patterns:
      - pattern: "FuelLevel updated"
        expected: present_during_stimulus
      - pattern: "CAN timeout"
        expected: present_during_invalid
      - pattern: "FATAL"
        expected: absent

# How to determine pass/fail
pass_criteria:
  - id: visual_fuel_change
    type: manual_visual
    observation_ref: fuel_ring_visual
    pass_condition: |
      Compare screenshots across fuel_low, fuel_mid, fuel_high:
      - Ring fill level visibly increases from low → mid → high
      - Color transitions: red → yellow → green
    failure_signal: "Screenshots identical across different fuel levels"

  - id: invalid_handling
    type: manual_visual
    observation_ref: fuel_numeric_display
    pass_condition: "When fuel_invalid stimulus applied, display shows '--' not a number"
    failure_signal: "Display shows a numeric value during invalid signal"

  - id: screenshot_geometry
    type: auto
    check: png_dimensions_match
    expected: {width: 1024, height: 600}
    failure_signal: "Screenshot dimensions don't match display resolution"

  - id: no_fatal_errors
    type: auto
    observation_ref: board_log_check
    check: pattern_absent
    pattern: "FATAL"
    failure_signal: "FATAL error found in board log during test"

  - id: can_signal_received
    type: auto
    observation_ref: board_log_check
    check: pattern_present
    pattern: "FuelLevel updated"
    failure_signal: "Board log doesn't show FuelLevel signal reception"

# What's automated vs manual
automation_plan:
  automated:
    - description: "CANSimService stimulus injection"
      provider: cansim
      sequences: [fuel_low, fuel_mid, fuel_high, fuel_invalid]

    - description: "Board screenshot capture"
      provider: target_automation
      actions: [goto_page main_panel, capture_screenshot]

    - description: "Screenshot geometry validation"
      check: png_dimensions_match

    - description: "Board log collection"
      method: scp_pull
      source: "/userdata/media/EXM.log"

    - description: "Board log pattern checking"
      checks: [no_fatal_errors, can_signal_received]

  manual:
    - description: "Visual comparison of fuel ring across states"
      reviewer: human
      criteria: visual_fuel_change

    - description: "Invalid signal handling verification"
      reviewer: human
      criteria: invalid_handling

    - description: "Final acceptance of all evidence"
      gate: human_review.final

# Known gaps and risks
known_gaps:
  - "Fuel level at exact boundary values (e.g., 25%, 75%) not tested"
  - "Wave filter settling time (DashBoardFuelLevel_WaveFilterTimer) is approximate; actual device may differ"
  - "Multi-channel simultaneous CAN signal interaction not covered"
  - "Power-cycle recovery after fuel level display not tested"

risks:
  - severity: medium
    description: "CANSimService may timeout if WSL gateway is slow"
    mitigation: "Pre-check /health endpoint; retry once on timeout"
  - severity: low
    description: "Screenshot timing may capture mid-transition frame"
    mitigation: "Use settle_ms > wave filter period (2500ms > 2000ms)"
```

### 11.2 How Test Design Gates Verification

The `test_design` recipe has `review: required`. This means:

1. After the test_design evidence is produced, the DAG engine checks for a `reviewed` event with `status: accepted`
2. If no such event exists, all nodes that depend on `test_design` are considered **blocked**
3. `ef satisfy` will pause and prompt: `"test_design pending review"`
4. Only after `ef review test_design <req> --accept` will downstream execution continue

This ensures:
- No verification can happen without a reviewed test plan
- CAN stimulus sequences are defined and approved before injection
- Target automation actions are planned before execution
- Pass/fail criteria are agreed upon before judging results

---

## 12. Project Layout

The project layout below is the future full target-device layout. In v0.3.0, Python plugins and run metadata are supported, while CANSim, target automation, and real board artifacts remain deferred. The checked-in `examples/exm-k` reference is still a smaller simulated local/manual layout.

### 12.1 Directory Structure

```text
project-root/
  ef.yaml                                   # main configuration (committed)

  .ef/
    profiles/
      exm-k/
        profile.yaml                        # build/deploy/target config (committed)
        local.env.yaml                      # local overrides, secrets (gitignored)
        cansim_sequences/                   # CAN signal definition files (committed)
          fuel_level_low.signals.json
          fuel_level_high.signals.json
          fuel_level_mid.signals.json
          fuel_gauge_sweep.sequence.json
          urea_level_green_band.sequence.json

    requirements/                           # requirement definitions (committed)
      REQ-EXM-FUEL-GAUGE-001.yaml
      REQ-EXM-TOOL-PRESSURE-001.yaml
      REQ-EXM-LOCAL-UNLOCK-001.yaml

    recipes/                                # recipe definitions (committed)
      build.yaml
      deploy.yaml
      test_design.yaml
      verify.can_stimulus.yaml
      verify.screenshot.yaml
      verify.comparison.yaml
      verify.log.yaml
      human_review.final.yaml

    plugins/                                # Python recipe plugins (committed)
      __init__.py
      unlock_automation.py
      custom_comparison.py

    evidence.jsonl                           # append-only event log (gitignored)

    artifacts/                              # produced evidence files (gitignored)
      REQ-EXM-FUEL-GAUGE-001/
        build/
          build.log
          EXM-K
        deploy/
          deploy.log
          health_result.json
        test_design/
          test_design.yaml
        verify.can_stimulus/
          cansim_stimulus.log
          stimulus_results.json
        verify.screenshot/
          screenshot_fuel_low.png
          screenshot_fuel_mid.png
          screenshot_fuel_high.png
          screenshot_fuel_invalid.png
          target_automation.log
        verify.comparison/
          comparison_report.json
          comparison.log
        verify.log/
          board_log.txt
          log_analysis.json
        human_review.final/
          acceptance.yaml

    runs/                                   # run metadata (gitignored)
      ef-20260430-001.yaml
      ef-20260430-002.yaml

    knowledge/                              # optional knowledge refs (committed)
      providers.yaml
```

### 12.2 .gitignore Entries

```gitignore
# EmbeddedFlow - gitignored by default
.ef/evidence.jsonl
.ef/artifacts/
.ef/runs/
.ef/profiles/*/local.env.yaml
.ef/profiles/*/local.secrets.env
```

### 12.3 Main Configuration (`ef.yaml`)

```yaml
# ef.yaml - EmbeddedFlow project configuration
project:
  id: exm-k
  name: "EXM-K"
  description: "K系列挖机显示器1代项目"
  repo_root: "."
  app_root: "EXM-K"

# Default profile to use when --profile not specified
default_profile: exm-k

# Global recipe defaults
recipe_defaults:
  timeout: 300
  shell: /bin/bash
  retry:
    max_attempts: 1
    interval_seconds: 5

# Knowledge provider (optional)
knowledge:
  provider: card_kb           # none | markdown_index | card_kb | custom
  path: "EXM-K/docs/ai-kb/"
  index: "EXM-K/docs/ai-kb/index/project-index.yaml"

# Source verification policy
policy:
  source_verification: required
  evidence_required: true
  test_design_review: required
  final_acceptance: required
  allow_stale_close: false

# Template variables available globally
vars:
  display_resolution: "1024x600"
  default_settle_ms: 2500
  default_screenshot_format: png
```

### 12.4 Profile Configuration

This production-board profile shape is retained as real-target roadmap material. v0.3.0 supports SSH/SCP targets in principle, but real EXM-K VM or board credentials are not required for the release.

```yaml
# .ef/profiles/exm-k/profile.yaml
id: exm-k
name: "EXM-K Kilo Production Board"
description: "ARM RV1126 OpenWrt board, 1024x600 display"

build:
  system: qmake
  entry: "EXM-K/EXM-K.pro"
  working_dir: "EXM-K/build/kilo"
  command: "{{build_env.qmake_path}} ../../EXM-K.pro && make -j4"
  artifact_path: "EXM-K/build/kilo/EXM-K"
  artifact_type: arm-elf

deploy:
  target_kind: openwrt_board
  deploy_dir: "/userdata/media/custom/EXM/"
  copy_targets:
    - src: "EXM-K/build/kilo/EXM-K"
      dst: "/userdata/media/custom/EXM/EXM-K"
  backup_strategy: backup_existing_binary
  start_command: "cd /userdata/media/custom && sh ./startApp.sh >/userdata/media/startApp_exm.log 2>&1 &"
  health_checks:
    - "pgrep EXM-K"
    - "test -f /userdata/media/EXM.log"
  stop_wait_seconds: 12
  startup_timeout_seconds: 40

verify:
  default_testcases:
    - build_smoke
    - deploy_smoke
    - fuel_gauge_sweep
  cansim_channel: "board_can1_rx_via_usb2"

targets:
  vm:
    description: "Build VM (Ubuntu with ARM cross-toolchain)"
    host: "{{local_env.targets.vm.host}}"
    port: "{{local_env.targets.vm.port}}"
    user: "{{local_env.targets.vm.user}}"
    auth_mode: "{{local_env.targets.vm.auth_mode}}"
  board:
    description: "Target board (RV1126 OpenWrt)"
    host: "{{local_env.targets.board.host}}"
    port: "{{local_env.targets.board.port}}"
    user: "{{local_env.targets.board.user}}"
    auth_mode: "{{local_env.targets.board.auth_mode}}"
  cansim:
    description: "CANSimService endpoint"
    host: auto              # auto-detect WSL gateway
    port: 18766
    transport: http
    timeout_seconds: 10
```

### 12.5 Local Environment (gitignored)

This real-target local environment file is where SSH/SCP target values would live. Real VM, board, and CANSim values are not required for v0.3.0 and must not be committed.

```yaml
# .ef/profiles/exm-k/local.env.yaml
# Machine-specific overrides. NEVER commit this file.
targets:
  vm:
    host: "192.168.24.129"
    port: 22
    user: "zoomlion"
    auth_mode: "password"
    password_env: "EF_VM_PASSWORD"
  board:
    host: "192.168.0.149"
    port: 22
    user: "root"
    auth_mode: "password"
    password_env: "EF_BOARD_PASSWORD"

build_env:
  env_exports:
    STAGING_DIR: "/opt/rv1126_sdk/openwrt/staging_dir"
  qmake_path: "/opt/rv1126_sdk/openwrt/staging_dir/target-arm_cortex-a7+neon_glibc_eabi/host/bin/qmake"
  build_workdir_override: "/mnt/hgfs/code/work_code/exm-k-2024/EXM-K/build/kilo"
```

---

## 13. CANSimService Integration

### 13.1 Architecture Role

```text
Recipe: verify.can_stimulus (type: cansim)
  → CansimExecutor (deferred after v0.3)
    → HTTP client
      → CANSimService endpoint (WSL or remote)
        → CAN hardware interface
          → Target board CAN bus
```

### 13.2 Host Resolution

CANSimService host is resolved at recipe execution time:

1. Check `EF_CANSIM_HOST` environment variable override
2. If profile says `host: auto`:
   - Parse `/etc/resolv.conf` for WSL nameserver IP
   - Or parse `ip route show default` for gateway IP
   - Use detected gateway as CANSimService host
3. Otherwise use `host` value from profile

### 13.3 HTTP Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Pre-check: service available |
| `/channels` | GET | Pre-check: required CAN channel exists |
| `/signals/set` | POST | Set specific signal values |
| `/sequence/run` | POST | Run pre-defined signal sequence |
| `/periodic/start` | POST | Start periodic signal streaming |
| `/periodic/stop` | POST | Stop periodic streaming |

### 13.4 CAN Sequence File Format

```json
{
  "id": "fuel_level_low",
  "description": "Set fuel level to 0% (empty tank)",
  "channel": "board_can1_rx_via_usb2",
  "signals": [
    {
      "name": "iFuelLevel_a",
      "pgn": "0x00FEF2",
      "spn": 96,
      "value": 0,
      "unit": "%"
    }
  ],
  "mode": "one_shot",
  "settle_ms": 2500
}
```

### 13.5 Integration with Test Design

The test_design evidence defines which sequences to run. The verify.can_stimulus recipe reads the test_design artifact and executes the specified sequences:

```text
test_design.yaml → stimulus.sequences[*].source → cansim_sequences/*.json → HTTP API calls
```

---

## 14. Target Automation Integration

### 14.1 Architecture Role

```text
Recipe: verify.screenshot (type: target_automation)
  → TargetAutomationExecutor (deferred after v0.3)
    → SSH tunnel to board
      → ZMQ PUB/SUB sockets
        → Board-side ZMQBroker
          → EXM-K TestAutomation module
            → Page navigation, screenshot, state query
```

### 14.2 Communication Protocol

- **Transport**: ZMQ PUB/SUB over SSH tunnel
- **Command topic**: `/BROKER/EXM/TestAutomation/Command`
- **Reply topic**: `/BROKER/EXM/TestAutomation/Reply`
- **Command port**: 5661 (on board)
- **Reply port**: 7661 (on board)
- **Format**: JSON messages

### 14.3 Available Commands

| Command | Description | Returns |
|---------|-------------|---------|
| `goto_page` | Navigate to a specific UI page | success/failure |
| `wait_page` | Wait until page is loaded | success/timeout |
| `wait_stable` | Wait for UI to stabilize | success |
| `capture_screenshot` | Capture current display | screenshot path |
| `get_state` | Query application state | state JSON |
| `press_button` | Simulate button press | success/failure |
| `input_text` | Input text to field | success/failure |

### 14.4 Screenshot Retrieval

After `capture_screenshot`, the executor:
1. Receives reply with remote screenshot path (e.g., `/tmp/screenshot_20260430_100300.png`)
2. Pulls file via SCP through the same SSH connection
3. Stores in `.ef/artifacts/<req-id>/verify.screenshot/`

---

## 15. Human Review Gates

### 15.1 Gate Types

| Gate | When | What's Reviewed | Who Decides |
|------|------|-----------------|-------------|
| test_design review | After test plan generated | Stimulus, observations, pass criteria, automation plan | Engineer |
| human_review.final | After all verification | Build/deploy/verify evidence, screenshots | Engineer or QA |

### 15.2 Review Workflow

```text
1. Recipe produces evidence (e.g., test_design.yaml)
2. Engine detects review: required
3. Engine appends 'produced' event with status: pass
4. Engine prints: "[wait] test_design -- pending human review"
5. ef satisfy stops (does not proceed to dependent nodes)
6. Human reviews artifacts
7. Human runs: ef review test_design REQ-xxx --accept --reviewer <name> --rationale "..."
8. Engine appends 'reviewed' event with review_status: accepted
9. Next ef satisfy call sees test_design as fully valid
10. Dependent nodes (verify.*) can now execute
```

### 15.3 Rejection and Rework

```bash
$ ef review test_design REQ-EXM-FUEL-GAUGE-001 --reject --reviewer liu --rationale "Missing invalid signal test case"
```

After rejection:
- Node status becomes `rejected`
- Agent/developer must regenerate the test design
- `ef recipe run test_design REQ-EXM-FUEL-GAUGE-001 --force` to re-produce
- New review required after re-production

---

## 16. Knowledge Layer

### 16.1 Principle

```text
Knowledge Base: Optional
Discovery: First (always works without knowledge)
Promote: Only stable, repeated, decision-relevant findings
```

### 16.2 Integration with Evidence-DAG

Knowledge assists two operations:
1. **ef context**: includes relevant knowledge refs in context output
2. **test_design generation**: AI agent uses knowledge to inform test design

### 16.3 Knowledge Levels

```text
Level 0: No Knowledge Base
  - Agent uses ef context + source code exploration
  - Works for new, small, or short-term projects

Level 1: Lightweight Knowledge Hints
  - Small project map, high-risk paths, build/deploy notes
  - Referenced in ef.yaml knowledge.path

Level 2: Structured Knowledge Provider
  - EXM-K AIKB-style cards (modules, flows, change-patterns, impact-rules)
  - Full card_kb provider with index routing
```

### 16.4 Knowledge in Context Response

```yaml
# Part of ef context output when knowledge is configured
knowledge:
  provider: card_kb
  path: "EXM-K/docs/ai-kb/"
  relevant_cards:
    - path: "cards/change-patterns/update-page-state-display.yaml"
      relevance: "Requirement involves UI state change based on CAN signal"
    - path: "cards/flows/protocol-to-cache-to-display.yaml"
      relevance: "Shows signal flow from CAN bus to UI display"
    - path: "cards/modules/communication-backbone.yaml"
      relevance: "FuelLevelHandler is part of communication module"
  discovery_hints:
    - "Check DashBoardFuelLevel.cpp for wave filter timer logic"
    - "Check CANBus/FuelLevelHandler.cpp for signal parsing"
    - "Check DataCache for intermediate value storage"
```

---

## 17. Migration from CodexFlow

### 17.1 Concept Mapping

| CodexFlow Concept | Evidence-DAG Equivalent |
|---|---|
| `STAGE_ORDER` (linear list) | DAG `depends_on` edges (graph) |
| `STAGE_DEPENDENCIES` dict | `depends_on` field in each recipe |
| Stage: intake | Implicit (requirement creation) |
| Stage: solution | Implicit (part of implementation) |
| Stage: test_design | Evidence node: `test_design` (review: required) |
| Stage: implement | Not a DAG node (implementation happens externally) |
| Stage: build | Evidence node: `build` |
| Stage: deploy | Evidence node: `deploy` |
| Stage: board_verify | Evidence nodes: `verify.*` (multiple) |
| Stage: archive | Implicit (all evidence satisfied = closed) |
| `manifest.yaml` (mutable state) | `evidence.jsonl` (append-only events) |
| `Adapter` class + `Registry` | Recipe YAML + optional Python plugin |
| `ExmKiloBuildAdapter` | Recipe: `build.yaml` (type: shell, remote: true) |
| `ExmBoardDeployAdapter` | Recipe: `deploy.yaml` (type: shell, steps) |
| `ExmBoardVerifyAdapter` | Recipe: `verify.*.yaml` (multiple nodes) |
| `CansimServiceHttpStimulusAdapter` | Recipe: `verify.can_stimulus.yaml` (type: cansim) |
| `WorkflowPacket` (push to agent) | `ef context` (pull from agent) |
| `codexflow.py run init` | `ef satisfy REQ-xxx` (auto-creates run) |
| `codexflow.py stage build --execute` | `ef satisfy REQ-xxx` (auto-decides what to execute) |
| `codexflow.py run close` | Implicit (all evidence satisfied) |
| `codexflow.py run human-acceptance` | `ef review human_review.final REQ-xxx --accept` |
| Testcase YAML in `profiles/exm-k/testcases/` | Requirement YAML in `.ef/requirements/` |
| CAN sequence files | Same files, moved to `.ef/profiles/exm-k/cansim_sequences/` |
| Profile: `profile.yaml` | Same structure at `.ef/profiles/exm-k/profile.yaml` |
| Profile: `local.env.yaml` | Same structure at `.ef/profiles/exm-k/local.env.yaml` |
| `TODO.md` / `DONE.md` | RequirementLedger (future), requirements/ directory |
| Evidence buckets (build_logs, screenshots) | `.ef/artifacts/<req>/<node>/` |

### 17.2 What Can Be Reused

**Reuse directly (as library code)**:
- `codex_version/tools/lib/runner.py` — SSH/SCP command execution
- `codex_version/tools/lib/cansim.py` — CANSim host resolution + HTTP
- `codex_version/tools/lib/evidence.py` — Artifact file writing helpers

**Reuse with adaptation**:
- `codex_version/tools/lib/test_design.py` — Validation logic for test design schema
- `codex_version/tools/lib/manifest.py` — Atomic file write patterns

**Do not reuse (replaced by DAG)**:
- `codex_version/tools/lib/models.py` — Stage ordering, manifest creation
- `codex_version/tools/lib/registry.py` — Adapter registry
- `codex_version/tools/cli/codexflow.py` — CLI and stage-based workflow logic

### 17.3 Coexistence Period

During migration, both systems can coexist:
- `codex_version/` directory remains for ongoing work
- `.ef/` directory is added alongside
- Same profile data, same CAN sequences, same targets
- Gradually move requirements from CodexFlow to EmbeddedFlow

---

## 18. v0.3.0 Release Deliverables

### 18.1 Minimum Viable Feature Set

| # | Deliverable | Description |
|---|---|---|
| 1 | CLI skeleton | `ef` command with subcommands, argument parsing (click or argparse) |
| 2 | `ef init` | Create `.ef/` directory structure |
| 3 | Config loading | Parse `ef.yaml`, `profile.yaml`, `local.env.yaml` |
| 4 | Template engine | `{{variable}}` expansion in recipes |
| 5 | Source hash | SHA-256 computation for watched files |
| 6 | Recipe hash | SHA-256 computation for recipe definitions |
| 7 | DAG builder | Construct graph from requirements + recipes |
| 8 | Topological sort | Kahn's algorithm with level detection |
| 9 | Validity checker | `is_valid()` with hash comparison and transitive check |
| 10 | Invalidation cascade | Transitive stale marking |
| 11 | Evidence store | JSONL append/read/query |
| 12 | `ef satisfy` | Full DAG execution with shell + manual types |
| 13 | Shell executor | Local subprocess and SSH remote command execution |
| 14 | Manual executor | Block + prompt + `ef review` |
| 15 | `ef status` | Per-node validity display |
| 16 | `ef what-next` | Next action suggestion |
| 17 | `ef context` | Pull-based context (full + scoped) |
| 18 | `ef evidence list/show/invalidate` | Evidence management |
| 19 | `ef dag` | Text-mode DAG visualization |
| 20 | `ef review` | Human review recording |
| 21 | EXM-K profile | Simulated local reference profile + build/deploy recipes |

### 18.2 Implemented through v0.3.0

- SSH remote shell recipes
- SCP artifact retrieval and `type: scp` recipe steps
- Multi-step shell recipes
- `agent_task` recipe type (external-agent handoff protocol)
- `python` recipe type (plugin-based recipes)
- Parallel execution (`--jobs N`)
- Test design schema validation
- `ef evidence compact`
- `ef run list/show` run history
- `ef recipe complete` for completed external-agent artifacts

### 18.3 Deferred after v0.3.0

- Real EXM-K target smoke with VM or board credentials
- CANSim recipe type and CANSimService integration
- Target automation recipe type and ZMQ bridge
- Target-device screenshot/log automation closed loop
- Knowledge provider integration (`card_kb`)
- Evidence export/import
- Reporting / summary generation (`ef render`)
- CAN sequence file management utilities
- RequirementLedger integration (GitHub Issues, TODO.md sync)

### 18.4 Implementation Phases

```text
Phase 1: Foundation (2 weeks)
  - Project structure (pyproject.toml, src/embeddedflow/)
  - CLI skeleton with click
  - ef init command
  - Config loading (ef.yaml, profile, local.env)
  - Template variable resolution engine (Jinja2-lite)
  - Evidence store (JSONL read/write/query)
  - Source hash computation (SHA-256 over file contents)
  - Recipe hash computation

Phase 2: DAG Core (2 weeks)
  - Requirement YAML loader with validation
  - Recipe YAML loader with validation
  - DAG construction from depends_on edges
  - Topological sort (Kahn's algorithm)
  - Validity checking algorithm (is_valid)
  - Invalidation cascade logic
  - ef status command
  - ef dag command (text mode)

Phase 3: Execution (2 weeks)
  - ef satisfy command (full flow)
  - Shell recipe executor (local subprocess)
  - Shell recipe executor (remote via SSH, reuse runner.py patterns)
  - SCP file copy (artifact retrieval)
  - Multi-step recipe support (steps array)
  - Manual recipe executor (block + prompt)
  - ef review command
  - ef what-next command
  - Artifact directory management

Phase 4: AI Interface (1 week)
  - ef context command (full context)
  - ef context --need (scoped context)
  - ef recipe complete (agent evidence reporting)
  - ef evidence list/show/invalidate
  - Output format support (yaml, json, markdown)

Phase 5: EXM-K Integration (1 week)
  - Write exm-k profile.yaml + local.env.yaml
  - Write build.yaml recipe
  - Write deploy.yaml recipe
  - Write test_design.yaml recipe (manual or agent_task-produced artifact)
  - Write human_review.final.yaml recipe
  - Simulated smoke: ef satisfy dry-run with local build + deploy
  - Deferred after v0.3.0: end-to-end test with build + deploy on real VM/board
  - Incremental test: modify source → ef status shows stale → ef satisfy re-builds
  - Migration guide document
```

---

## 19. Key Risks and Guardrails

Risk: DAG model becomes too complex for simple requirements.

Guardrail: A requirement with only `[build, deploy]` evidence is two nodes — simpler than the 8-stage CodexFlow pipeline. Complexity scales with need, not with ceremony.

Risk: Source hash computation is slow for large codebases.

Guardrail: Hash computation is lazy (only at `ef status` / `ef satisfy` time). Use incremental hashing with cached results. Glob expansion is the bottleneck — cache file lists with mtime checks.

Risk: AI agents don't understand the pull-based context model.

Guardrail: `ef what-next` gives explicit instructions. `ef context --need` gives exactly what's needed. The agent can always fall back to `ef satisfy` which handles everything automatically.

Risk: Evidence JSONL grows unbounded.

Guardrail: Old events beyond the latest valid/invalid cycle per node are safe to compact. v0.3.0 includes the `ef evidence compact` command.

Risk: Test design evidence becomes a rubber-stamp gate.

Guardrail: The `manual` review requires explicit rationale. `ef review --accept` without `--rationale` is rejected. The review event is part of the audit trail.

Risk: Remote recipe execution (SSH) hangs or times out.

Guardrail: All recipes have configurable timeouts. Shell executor uses subprocess with timeout. SSH commands use `-o ConnectTimeout=10`. Health checks have retry logic.

Risk: EXM-K product details leak into core.

Guardrail: All EXM-K-specific values live in `.ef/profiles/exm-k/` and `.ef/requirements/`. The core engine is project-agnostic. It executes recipes without understanding CAN signals or UI pages.

Risk: Concurrent ef satisfy invocations corrupt evidence.jsonl.

Guardrail: Evidence append uses OS-level file locking (fcntl). Run IDs are unique (timestamp + random). Parallel execution should stay within one orchestrated `ef satisfy --jobs N` invocation.

---

## 20. Decision Summary

The approved direction is:

- Build EmbeddedFlow as a **DAG-based evidence constraint solver**, not a stage-gate pipeline
- Three core concepts only: Requirement, Recipe, Evidence
- **Incremental execution** (Make-like): only re-run what's stale
- **Pull-based AI context**: agents query what they need via `ef context`
- **Test design as hard dependency**: `verify.*` nodes cannot run without reviewed test plan
- **Content hash validity**: not timestamps, not manual markers
- **Append-only event log**: immutable audit trail, state derived from events
- **Recipe-first adapter model**: YAML definitions for simple cases, Python plugins for complex
- **Python implementation**: AI-friendly, consistent with existing codexflow.py
- **EXM-K as first reference**: same targets, same CAN sequences, same knowledge base
- v0.3.0 validates the workflow core with shell, manual, agent_task, Python plugin, parallel execution, evidence compaction, and run history before real CANSim/target automation integration.
