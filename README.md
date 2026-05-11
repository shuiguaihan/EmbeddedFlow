# EmbeddedFlow

EmbeddedFlow is a project-local Evidence-DAG CLI for embedded product software workflows. A requirement is complete when all evidence nodes in its DAG are valid.

## Quick Start

```bash
PYTHONPATH=src python3 -m embeddedflow.cli init --profile demo
PYTHONPATH=src python3 -m embeddedflow.cli status REQ-1
PYTHONPATH=src python3 -m embeddedflow.cli satisfy REQ-1 --dry-run
```

v0.3 extends the core model:

- Requirement YAML declares required evidence.
- Recipe YAML declares how to produce evidence and dependencies.
- `.ef/evidence.jsonl` stores append-only evidence events.
- Source and recipe hashes drive lazy stale detection.
- Local and SSH `shell` recipes, multi-step recipes, `manual`, `agent_task`, and Python plugin recipe types are supported.

## v0.3 Support Matrix

| Capability | v0.3 status | Notes |
|------------|-------------|-------|
| Local shell recipes | Supported | Run through local subprocess execution. |
| SSH remote shell recipes | Supported | `remote: true` runs through OpenSSH using targets from `.ef/profiles/<profile>/local.env.yaml`. |
| SCP/artifact transfer from remote hosts | Supported | `copy_to_local: true` artifacts and `type: scp` recipe steps use `scp`. |
| Multi-step shell recipes | Supported | `steps` run sequentially with per-step logs, retries, timeouts, and optional ignored failures. |
| Manual review gates | Supported | `review: required` nodes stay pending until `ef review ... --accept --rationale <text>`. |
| `agent_task` recipe type | Supported | Prepares `instructions.md` and `context.json`; external agents report output with `ef recipe complete`. |
| `python` plugin recipe type | Supported | Loads `.ef/plugins/<plugin>.py` with importlib and calls `run(...)`. |
| Parallel execution (`--jobs N`) | Supported | Executes independent nodes in the same DAG level concurrently. |
| Test design schema validation | Supported | `test_design_v1` artifacts are validated when completing `agent_task` recipes. |
| Evidence compaction | Supported | `ef evidence compact` keeps latest node cycles and relevant reviews/invalidations. |
| Run history | Supported | `ef run list` and `ef run show <run-id>` read `.ef/evidence.jsonl`. |
| Simulated EXM-K example | Supported | `examples/exm-k` is a local shell/manual reference smoke, not a real board flow. |
| Real EXM-K target smoke | Deferred | No VM, board credentials, CANSim, ZMQ, or target automation is required for automated readiness. |
| CANSim and target automation | Deferred | Planned after the recipe and evidence protocol remain stable. |
| Git status, commits, tags | Not readiness criteria | Product readiness is proven by deterministic CLI tests and smoke commands. |

## Python Plugin Recipes

Python recipe plugins live under `.ef/plugins/`. A recipe with `type: python` loads `.ef/plugins/<plugin>.py`, where `<plugin>` comes from the recipe `plugin` field or falls back to the recipe id.

```python
# .ef/plugins/my_plugin.py
from pathlib import Path

from embeddedflow.models import Recipe


def run(root: Path, req_id: str, recipe: Recipe, config: dict) -> dict:
    return {"status": "pass", "artifacts": []}
```

The return value must be a dict with `status` set to `"pass"` or `"fail"`. Optional keys are `artifacts` and `error`.

## Development Verification

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m compileall -q src tests
```
