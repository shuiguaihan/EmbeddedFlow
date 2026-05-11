# EmbeddedFlow Handoff

Current state: `$ralph` completed `.omx/plans/evidence-dag-v0.1-implementation-plan.md`. The v0.1 boundary is now implemented and documented as local shell + manual gates + simulated EXM-K only.

Verified facts:
- Tests cover `remote: true` unsupported/no-pass-evidence, manual review rationale, EXM-K simulated DAG/dry-run, and docs overclaim regression.
- `README.md`, `DESIGN-evidence-dag.md`, and `DESIGN-evidence-dag-zh.md` now mark SSH/SCP/real board/CANSim/target automation/agent_task/python/`--jobs` as deferred roadmap.
- Final architect pass approved; deslop found no masking fallback slop and only cleaned test spacing.
- Post-deslop checks passed: 13 tests OK, compileall OK, CLI help OK, demo dry-run OK, EXM-K DAG/dry-run OK, no `remote:` in EXM-K recipes.

Next actions:
1. If needed, repair git metadata so `git status`, diff, commit, and tag can work.
2. If continuing product work, start a separate v0.2 plan for SSH/SCP/real-board/CANSim/target automation.

Recheck before release:
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v`
- `PYTHONPYCACHEPREFIX=/tmp/embeddedflow-compileall-cache PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m compileall -q src tests`
- CLI help, demo dry-run, EXM-K DAG/dry-run, and `rg -n "remote:" examples/exm-k/.ef/recipes`.

Known blocker: Git metadata is unavailable from this directory, so no commit/tag was made. Legacy `current_*` migration input used: no.
