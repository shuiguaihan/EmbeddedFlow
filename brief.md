# EmbeddedFlow Handoff

Current state: v0.3.0 release-ready after local verification on 2026-06-02. The Evidence-DAG workflow core is implemented and verified; real target-device automation remains deferred.

Release position:
- v0.3.0 is an Evidence-DAG workflow prototype release, not a real EXM-K board automation release.
- CLI workflow core, incremental evidence validity, manual review gates, SSH/SCP shell execution, multi-step recipes, agent tasks, Python plugin recipes, parallel execution, schema validation, evidence compaction, and run history are implemented.
- `examples/demo` and `examples/exm-k` are supported reference examples; `examples/exm-k` remains a simulated local shell/manual smoke.
- Real EXM-K target smoke, CANSim, ZMQ bridge, and target automation are deferred to the next real-target integration phase.

Release checklist:
1. Keep `pyproject.toml` and `src/embeddedflow/__init__.py` at `0.3.0`.
2. Keep `README.md` as the canonical v0.3 support matrix.
3. Keep design docs clear that older v0.1/v0.2 sections are historical/roadmap context when they conflict with the v0.3 support matrix.
4. The verification commands below passed locally on 2026-06-02.
5. If verification passes and the working tree contains only release cleanup changes, commit and tag `v0.3.0`.

Verified before release:
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m compileall -q src tests`
- CLI help: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m embeddedflow.cli --help`
- Demo smoke: `cd examples/demo && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../../src python3 -m embeddedflow.cli status REQ-1`
- Demo dry-run: `cd examples/demo && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../../src python3 -m embeddedflow.cli satisfy REQ-1 --dry-run`
- EXM-K DAG smoke: `cd examples/exm-k && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../../src python3 -m embeddedflow.cli dag REQ-EXM-FUEL-GAUGE-001 --format json`
- EXM-K dry-run: `cd examples/exm-k && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../../src python3 -m embeddedflow.cli satisfy REQ-EXM-FUEL-GAUGE-001 --dry-run`

Known boundaries:
- Python 3.10+ is required.
- `agent_task` prepares instructions/context for an external agent; it does not call AI APIs itself.
- No VM credentials, board credentials, CANSim service, ZMQ bridge, or target-device screenshot/log automation is required for v0.3.0 readiness.
