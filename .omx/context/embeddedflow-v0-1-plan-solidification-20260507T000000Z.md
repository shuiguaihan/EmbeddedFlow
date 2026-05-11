# EmbeddedFlow v0.1 Plan Solidification Context

Task statement: 固化当前 EmbeddedFlow Evidence-DAG MVP 的 v0.1 交付计划，评估 baseline、剩余范围、架构取舍、测试规格、EXM-K 集成边界，并输出下一轮可执行步骤。

Desired outcome: 一个经 Planner/Architect/Critic 共识确认的 v0.1 plan，包含 ADR、验收标准、测试路径、执行 staffing guidance 和 handoff hints。

Known facts/evidence:
- Design sources: DESIGN-evidence-dag.md and DESIGN-evidence-dag-zh.md.
- Existing plan: .omx/plans/evidence-dag-v0.1-implementation-plan.md.
- Implemented package: pyproject.toml and src/embeddedflow/.
- Implemented commands: init, status, dag, satisfy, review, context, what-next, evidence list/show/invalidate, recipe list/run/complete, profile list.
- Implemented v0.1 executors: local shell and manual. Remote shell currently not implemented.
- Tests: tests/test_core.py and tests/test_cli_integration.py cover template/hash, evidence store, DAG, init/status/dag/satisfy/review/context/invalidation, recipe/profile commands.
- Reported previous verification: 9 unittest tests passed, compileall passed, CLI help worked, demo dry-run worked, EXM-K DAG levels parsed.
- Examples: examples/demo and examples/exm-k. EXM-K is simulated, not real target integration.
- Git state issue: .git exists as read-only stub; git init/status failed previously, so commits are blocked until repo metadata is repaired.

Constraints:
- Planning only; do not implement during ralplan.
- Current sandbox is read-only; writes require escalation.
- Network restricted; no dependency fetching.
- Preserve v0.1 design guardrail: shell/manual first; CANSim, target_automation, agent_task, parallel jobs deferred unless consensus changes scope.

Unknowns/open questions:
- Whether remote SSH shell belongs in v0.1 must-have or v0.1.1 follow-up.
- How deep real EXM-K integration should go before v0.1 completion.
- Whether git repo repair is part of product v0.1 or a separate hygiene task.
- Whether installed console script verification is required or module CLI is enough for v0.1.

Likely codebase touchpoints:
- src/embeddedflow/cli.py
- src/embeddedflow/executors/shell.py
- src/embeddedflow/status.py
- src/embeddedflow/evidence.py
- src/embeddedflow/dag.py
- tests/test_cli_integration.py
- examples/exm-k/.ef/**
