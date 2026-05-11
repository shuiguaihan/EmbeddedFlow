# Evidence-DAG v0.1 Solidification Plan

> Status: RALPLAN-DR consensus candidate. This artifact supersedes the earlier broad v0.1 implementation plan and current design overclaims where they implied SSH remote execution or real EXM-K board/VM smoke as v0.1 acceptance criteria.

## Goal

Solidify the current EmbeddedFlow Evidence-DAG MVP into a truthful v0.1 release boundary: local shell recipes, manual review gates, append-only evidence, deterministic DAG/status behavior, and simulated EXM-K reference smoke. Remote SSH/SCP, real target-board evidence, CANSim, target automation, agent-task recipes, parallel jobs, and git release hygiene are deferred or non-blocking unless a later plan explicitly changes scope.

## Baseline Verdict

Option A is the v0.1 baseline: local/manual MVP now; SSH remote, real EXM-K target smoke, CANSim/target automation, and git repair are deferred/non-blocking.

Evidence-backed current baseline:
- `ef init`, `.ef/` structure creation, profile scaffolding, and `.gitignore` entries exist.
- Requirement and recipe loading from `.ef/requirements` and `.ef/recipes` exists.
- DAG construction, levels, status derivation, and dry-run planning exist.
- Local `shell` recipes execute and capture stdout/stderr artifact logs.
- `manual` recipes produce instructions evidence; blocking acceptance requires `review: required` plus accepted review.
- Append-only `.ef/evidence.jsonl` event storage exists.
- CLI surface includes `evidence`, `recipe`, `context`, `what-next`, and `profile` commands.
- `examples/exm-k/.ef/**` is a simulated/local reference, not real board/SSH integration.

Known contradiction to close:
- The earlier plan/design language overclaimed v0.1 remote SSH/SCP and real EXM-K smoke. This plan reclassifies those as deferred design/roadmap items, not v0.1 acceptance.

## RALPLAN-DR Summary

### Principles

1. Truthful scope beats aspirational scope: docs and plans must describe what v0.1 actually supports.
2. Evidence integrity beats demo breadth: unsupported recipes must fail clearly without recording passing evidence.
3. Local reproducibility beats hardware dependence: v0.1 must be verifiable on a fresh local checkout.
4. Manual gates are first-class evidence nodes, not placeholders; gate recipes must use `review: required`.
5. Release blockers must be deterministic commands, not git metadata or unavailable hardware.

### Decision Drivers

1. Avoid false claims that v0.1 supports SSH/remote shell execution.
2. Preserve a coherent EXM-K reference without requiring proprietary hardware or credentials.
3. Lock current behavior with CLI integration assertions before release.
4. Keep git hygiene separate from product readiness.

### Viable Options

#### Option A — Local/manual MVP now; remote deferred. Chosen.

Pros:
- Matches current implementation and tests.
- Locally reproducible without credentials, VM, board, CANSim, or network.
- Minimizes false evidence risk.
- Provides a stable core for future real-target integrations.

Cons:
- Smaller than the original architecture prose implied.
- Requires explicit docs correction so users do not expect remote/real-board v0.1 support.

#### Option B — Include SSH remote shell in v0.1. Rejected.

Pros:
- Closer to early design language about shell recipes running locally or remotely.
- Better supports the long-term embedded target-device story.

Cons:
- Adds authentication, timeout, remote cwd/env, SCP/artifact-transfer, and environment risks.
- Requires new integration strategy or mocks; without real SSH coverage it could create false confidence.
- Expands scope late in v0.1 hardening.

#### Option C — Require real EXM-K target smoke before v0.1. Rejected.

Pros:
- Stronger proof of target-device evidence on a real reference project.
- Validates product positioning earlier.

Cons:
- Not reproducible in CI or by new contributors.
- Depends on board availability, credentials, network, VM/toolchain, and product-specific environment.
- Would mix core validation with EXM-K deployment risk.

#### Option D — Make git repair a release blocker. Rejected.

Pros:
- Improves normal release hygiene and enables commits/tags.

Cons:
- Git state is project hygiene, not Evidence-DAG runtime behavior.
- Current git metadata is broken/read-only; product readiness can still be proven via deterministic commands and artifacts.
- Should be tracked separately unless the user asks for commit/tag release work.

## v0.1 Scope Matrix

### Implemented / Baseline

- `ef init`, project structure, `.gitignore` entries.
- Requirement/recipe loading from `.ef/requirements` and `.ef/recipes`.
- DAG graph, topological levels, status, and dry-run planning.
- Local `shell` recipes with stdout/stderr artifact logs.
- `manual` recipes plus review-required gates.
- Append-only `.ef/evidence.jsonl` event model.
- `ef evidence list/show/invalidate`.
- `ef recipe list/run/complete`.
- `ef context` and `ef what-next`.
- `ef profile list`.
- Simulated EXM-K reference under `examples/exm-k/.ef/**`.

### Must-Close Before v0.1

1. Rewrite plan/docs to remove v0.1 remote shell and real-board claims.
2. Add unsupported-remote CLI integration test:
   - `remote: true` recipe exits nonzero.
   - stderr contains `remote shell recipes are not implemented in this v0.1 slice`.
   - `.ef/evidence.jsonl` is absent or contains no `event == "produced"` with `status == "pass"` for the remote node.
3. Add manual review assertions:
   - review-required manual nodes remain `pending_review` after recipe production.
   - nodes become `valid` only after `ef review <node> <req> --accept --rationale <text>`.
   - `ef review <node> <req> --accept` without `--rationale` exits nonzero and mentions `--accept requires --rationale`.
4. Add docs support matrix marking deferred items.
5. Add simulated EXM-K DAG/dry-run verification using `REQ-EXM-FUEL-GAUGE-001`.
6. Ensure release readiness text excludes `git status`, commits, and tags.

### Deferred

- SSH remote shell execution.
- SCP/artifact transfer from remote hosts.
- Real EXM-K target deploy/smoke.
- CANSim integration.
- Target automation/ZMQ/SSH tunnels.
- Agent-task recipe type.
- Python plugin recipe type.
- Parallel jobs / `--jobs`.
- Evidence compaction.
- Multi-operator/concurrent guarantees beyond current append locking.

### Non-Blockers

- Dirty/broken git status.
- Commit creation.
- Tag creation.
- Git history repair.
- Real board credentials.
- Remote VM access.

## Execution Plan For Next Lane

### Task 1 — Canonical Plan And Docs Truth Correction

Files:
- Modify: `.omx/plans/evidence-dag-v0.1-implementation-plan.md`
- Modify: `README.md`
- Modify: `DESIGN-evidence-dag.md`
- Modify: `DESIGN-evidence-dag-zh.md`

Acceptance criteria:
- This plan remains Option A: local/manual MVP, remote deferred.
- `README.md` contains a v0.1 support matrix:
  - Local shell: supported.
  - Manual review gates: supported.
  - Simulated EXM-K example: supported.
  - SSH remote shell: deferred.
  - Real EXM-K target smoke: deferred.
  - CANSim/target automation/agent_task/python recipe/jobs: deferred.
  - Git status/commits/tags: not product readiness criteria.
- `DESIGN-evidence-dag.md` and `DESIGN-evidence-dag-zh.md` mark SSH/SCP/real-target sections as future-facing roadmap where they previously implied v0.1 support.
- A “supersedes current design overclaims” note appears in the plan/design docs.

### Task 2 — Remote Unsupported Boundary Test

Files:
- Modify: `tests/test_cli_integration.py`

Test setup:
- Create a temp project with req id `REQ-REMOTE`.
- Add a shell recipe node, for example `remote_build`, with `remote: true`.
- Run `ef satisfy REQ-REMOTE` with `check=False`.

Acceptance assertions:
- `returncode != 0`.
- `stderr` contains `remote shell recipes are not implemented in this v0.1 slice`.
- Evidence file is absent or contains no event satisfying:
  - `event == "produced"`
  - `node == "remote_build"`
  - `status == "pass"`

### Task 3 — Manual Review Gate Regression

Files:
- Modify: `tests/test_cli_integration.py`
- Optionally modify: `README.md` to document exact command examples.

Acceptance assertions:
- After `ef satisfy REQ-1`, `human_review.final` status is `pending_review`.
- `ef review human_review.final REQ-1 --accept` exits nonzero.
- stderr contains `--accept requires --rationale`.
- `ef review human_review.final REQ-1 --accept --reviewer qa --rationale "artifact checked"` succeeds.
- Status becomes `valid` after accepted review.

Manual gate rule:
- Any manual node intended to block completion must include `review: required`.
- Manual recipes without `review: required` are non-blocking instruction/evidence recipes, not acceptance gates.

### Task 4 — EXM-K Simulated Smoke Test

Files:
- Modify: `tests/test_cli_integration.py` or add a focused test module.
- Review consistency: `examples/exm-k/.ef/**`.

Acceptance assertions:
- Running from `examples/exm-k`:
  - `ef dag REQ-EXM-FUEL-GAUGE-001 --format json` returns levels exactly:
    `[["test_design"], ["build"], ["deploy"], ["human_review.final"]]`.
  - `ef satisfy REQ-EXM-FUEL-GAUGE-001 --dry-run` stdout contains `[run]   test_design`, `[run]   build`, `[run]   deploy`, and `[run]   human_review.final`, and does not require SSH, VM, board credentials, CANSim, ZMQ, or real EXM-K tools.
- `rg -n "remote:" examples/exm-k/.ef/recipes` returns no matches for the v0.1 baseline.
- `examples/exm-k/.ef/recipes/test_design.yaml` and `examples/exm-k/.ef/recipes/human_review.final.yaml` contain `review: required`.
- No `examples/exm-k/.ef/recipes/*.yaml` uses `remote: true` for v0.1 baseline.

### Task 5 — Release Verification And Evidence Capture

Files:
- No source changes unless verification fails.
- Conditional write scope: `src/embeddedflow/cli.py` may be touched only if the new remote/manual tests expose a behavior gap.
- Optional output artifact: `.omx/plans/evidence-dag-v0.1-verification.md`.

Acceptance criteria:
- All commands in the verification checklist pass.
- Final report records exact commands and outcomes.
- Git commands are not required to prove product readiness.

## Exact Verification Checklist

Run from repo root:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
```

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m compileall -q src tests
```

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m embeddedflow.cli --help
```

Demo dry-run:

```bash
cd examples/demo
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../../src python3 -m embeddedflow.cli satisfy REQ-1 --dry-run
```

Simulated EXM-K DAG:

```bash
cd examples/exm-k
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../../src python3 -m embeddedflow.cli dag REQ-EXM-FUEL-GAUGE-001 --format json
```

Simulated EXM-K dry-run:

```bash
cd examples/exm-k
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../../src python3 -m embeddedflow.cli satisfy REQ-EXM-FUEL-GAUGE-001 --dry-run
```

Required test-level evidence assertions:
- Remote unsupported path: nonzero, exact stderr substring, no produced/pass evidence event.
- Manual gate path: pending before review, accept-without-rationale fails, valid after accepted review with rationale.
- EXM-K smoke: exact DAG levels and local/simulated dry-run.
- Docs scope: support matrix marks remote SSH/CANSim/target automation/agent_task/python/jobs as deferred.
- Docs grepability: README/design docs contain explicit `supported`, `deferred`, and `not product readiness criteria` wording/rows.

### Non-Blocking Follow-Up

If manual review gates are intended to block downstream execution, add a follow-up test and implementation decision that a pending `review: required` upstream node prevents dependent nodes from running. Current v0.1 solidification requires correct pending/valid status semantics first.

## Risks Mapped To Mitigation Owner/File

| Risk | Owner/Lane | Files | Mitigation |
|---|---|---|---|
| Docs/plans keep claiming remote SSH support | writer/executor | `.omx/plans/evidence-dag-v0.1-implementation-plan.md`, `README.md`, `DESIGN-evidence-dag.md`, `DESIGN-evidence-dag-zh.md` | Rewrite support matrix and v0.1 scope language; label SSH/SCP as deferred. |
| Remote recipe failure records misleading pass evidence | test-engineer/executor | `tests/test_cli_integration.py`, `src/embeddedflow/cli.py` only if test fails | Assert nonzero exit, exact stderr substring, and no pass-produced event. |
| Manual gates become rubber stamps | test-engineer/writer | `tests/test_cli_integration.py`, `README.md` | Assert `pending_review` until accepted review with rationale; document exact review command. |
| EXM-K reference implies real board support | writer/executor | `examples/exm-k/.ef/**`, `README.md`, `DESIGN-evidence-dag.md`, `DESIGN-evidence-dag-zh.md` | Keep recipes simulated/local; document real target smoke as deferred. |
| Release readiness conflated with git hygiene | writer/planner | `README.md`, `.omx/plans/evidence-dag-v0.1-implementation-plan.md` | Explicitly list git status/commits/tags as non-blockers for product readiness. |
| Future roadmap gets lost when narrowing v0.1 | writer/architect | design docs and ADR | Preserve remote/real-target as v0.2+ roadmap, not deleted product vision. |

## ADR: Adopt Local/Manual EmbeddedFlow v0.1 And Defer Remote/Real-Target Support

### Decision

EmbeddedFlow v0.1 releases as a local/manual Evidence-DAG MVP.

Supported in v0.1:
- Project init.
- DAG/status/dry-run.
- Local shell recipes.
- Manual review gates.
- Append-only evidence.
- Context/evidence/recipe/profile CLI commands.
- Simulated EXM-K reference.

Deferred from v0.1:
- SSH remote shell.
- SCP/artifact transfer.
- Real EXM-K target smoke.
- CANSim.
- Target automation.
- Agent-task recipes.
- Python plugin recipes.
- Parallel jobs.

This ADR supersedes design overclaims in existing plan/design artifacts that describe remote SSH/SCP or real EXM-K target support as v0.1 behavior.

### Drivers

- Current implementation rejects `remote: true` recipes.
- Local/manual workflows are deterministic and testable.
- Real board/SSH support requires environment-specific credentials and integration coverage.
- Docs must preserve evidence truthfulness.

### Alternatives Considered

- Option A: Local/manual MVP now; remote deferred. Chosen because it matches implementation, is testable locally, and avoids false evidence claims.
- Option B: Include SSH remote in v0.1. Rejected because it adds auth/network/timeout/artifact-transfer risks and requires additional test infrastructure.
- Option C: Require real EXM-K target smoke before v0.1. Rejected because it makes release readiness dependent on unavailable hardware and credentials.
- Option D: Make git repair a release blocker. Rejected because git hygiene is not runtime product behavior and is not required to prove Evidence-DAG correctness.

### Why Chosen

This option closes v0.1 around the already working Evidence-DAG core, makes unsupported boundaries explicit and testable, and avoids shipping misleading evidence about remote or target-device execution.

### Consequences

- v0.1 is smaller but truthful and reproducible.
- Roadmap documentation must clearly distinguish future architecture from implemented release behavior.
- Remote recipe attempts must fail loudly and leave no passing evidence.
- Simulated EXM-K remains the first reference case; real EXM-K becomes a future integration milestone.

### Follow-ups

- v0.2 design/plan for SSH remote execution with timeout, auth config, SCP artifacts, and integration test strategy.
- Future real EXM-K smoke plan with credential boundaries and reproducible evidence capture.
- Future CANSim/target automation plan after local Evidence-DAG semantics are stable.
- Separate git metadata recovery plan if release commits/tags are required.

## Available-Agent-Types Roster

- `explore`: fast repository lookup and file/symbol mapping.
- `planner`: plan updates and sequencing.
- `architect`: architectural boundary review.
- `critic`: plan/design challenge and quality gate.
- `executor`: implementation and refactoring.
- `test-engineer`: tests, coverage, flaky-test hardening.
- `writer`: documentation, migration notes, release guidance.
- `verifier`: completion evidence, claim validation, test adequacy.
- `code-reviewer`: final code review across behavior, regressions, and tests.
- `debugger`: root-cause analysis if verification fails.

## Follow-Up Staffing Guidance

### Ralph Path

Recommended for this plan because work is bounded and sequential.

Suggested allocation:
- `ralph` owner / `executor` medium reasoning: edits tests/docs/examples according to this plan.
- Optional `explore` low reasoning: quick lookup for design overclaim locations.
- `verifier` high reasoning: reruns exact checklist and validates evidence before completion.
- Optional `writer` high reasoning: if docs/design wording becomes large.

Launch hint:

```text
$ralph "Execute .omx/plans/evidence-dag-v0.1-implementation-plan.md exactly: close v0.1 local/manual scope, add remote unsupported/no-pass-evidence tests, add manual review rationale tests, add EXM-K simulated smoke, update README/design docs support matrix, then run the verification checklist. Do not implement SSH remote support."
```

Ralph stop condition:
- Must-close tests and docs are implemented.
- Verification checklist passes.
- Final report includes changed files, commands run, evidence, and remaining v0.2 risks.

### Team Path

Use only if parallel speed matters.

Suggested lanes:
- `test-engineer`: owns `tests/test_cli_integration.py` remote/manual/EXM-K assertions.
- `writer`: owns `README.md`, `DESIGN-evidence-dag.md`, `DESIGN-evidence-dag-zh.md` support/deferred matrix.
- `executor`: owns `examples/exm-k/.ef/**` consistency checks only if examples need edits.
- `verifier`: runs final checklist after all write lanes land.
- `code-reviewer`: reviews for overclaiming, unsupported behavior, and test adequacy.

Launch hint:

```text
$team "Execute .omx/plans/evidence-dag-v0.1-implementation-plan.md with disjoint lanes: tests for remote unsupported/no pass evidence, manual review gates, EXM-K simulated smoke; docs support matrix in README and design docs; examples consistency; final verification. Do not implement SSH remote support."
```

Team verification path:
- Team proves tests pass, compileall passes, CLI help works, demo dry-run works, EXM-K DAG/dry-run works, and remote unsupported behavior records no pass evidence.
- Final verifier or Ralph reruns the full checklist before shutdown.
