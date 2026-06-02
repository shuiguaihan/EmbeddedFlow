# Changelog

## v0.3.0 - Evidence-DAG workflow prototype

Release status: release-ready after local verification on 2026-06-02.

### Supported

- Evidence-DAG core model: requirements declare evidence, recipes produce evidence, and `.ef/evidence.jsonl` records append-only events.
- Incremental validity: source and recipe hashes decide whether existing evidence remains valid.
- CLI workflow: `ef status`, `ef dag`, `ef satisfy`, `ef review`, and `ef context`.
- Local shell recipes, SSH remote shell recipes, SCP artifact transfer, and multi-step shell recipes.
- Manual review gates with required acceptance rationale.
- `agent_task` recipes that prepare instructions/context for external agents and accept completed artifacts through `ef recipe complete`.
- `python` plugin recipes loaded from `.ef/plugins/<plugin>.py`.
- Parallel execution through `ef satisfy --jobs N` for independent nodes in the same DAG level.
- `test_design_v1` schema validation for agent-produced test design artifacts.
- Evidence compaction through `ef evidence compact`.
- Run history through `ef run list` and `ef run show`.
- Reference examples in `examples/demo` and `examples/exm-k`.

### Deferred

- Real EXM-K target smoke with VM or board credentials.
- CANSim service integration.
- ZMQ bridge and target automation.
- Target-device screenshot/log automation closed loop.

### Verification

Verified on 2026-06-02:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m compileall -q src tests
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m embeddedflow.cli --help
```

Reference smoke commands:

```bash
cd examples/demo
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../../src python3 -m embeddedflow.cli status REQ-1
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../../src python3 -m embeddedflow.cli satisfy REQ-1 --dry-run

cd ../exm-k
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../../src python3 -m embeddedflow.cli dag REQ-EXM-FUEL-GAUGE-001 --format json
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../../src python3 -m embeddedflow.cli satisfy REQ-EXM-FUEL-GAUGE-001 --dry-run
```
