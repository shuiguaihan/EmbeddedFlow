# EmbeddedFlow

EmbeddedFlow is a project-local Evidence-DAG CLI for embedded product software workflows. A requirement is complete when all evidence nodes in its DAG are valid.

## Quick Start

```bash
PYTHONPATH=src python3 -m embeddedflow.cli init --profile demo
PYTHONPATH=src python3 -m embeddedflow.cli status REQ-1
PYTHONPATH=src python3 -m embeddedflow.cli satisfy REQ-1 --dry-run
```

v0.2 extends the core model:

- Requirement YAML declares required evidence.
- Recipe YAML declares how to produce evidence and dependencies.
- `.ef/evidence.jsonl` stores append-only evidence events.
- Source and recipe hashes drive lazy stale detection.
- Local and SSH `shell` recipes, multi-step recipes, and `manual` recipe types are supported.

## v0.2 Support Matrix

| Capability | v0.2 status | Notes |
|------------|-------------|-------|
| Local shell recipes | Supported | Run through local subprocess execution. |
| SSH remote shell recipes | Supported | `remote: true` runs through OpenSSH using targets from `.ef/profiles/<profile>/local.env.yaml`. |
| SCP/artifact transfer from remote hosts | Supported | `copy_to_local: true` artifacts and `type: scp` recipe steps use `scp`. |
| Multi-step shell recipes | Supported | `steps` run sequentially with per-step logs, retries, timeouts, and optional ignored failures. |
| Manual review gates | Supported | `review: required` nodes stay pending until `ef review ... --accept --rationale <text>`. |
| Run history | Supported | `ef run list` and `ef run show <run-id>` read `.ef/evidence.jsonl`. |
| Simulated EXM-K example | Supported | `examples/exm-k` is a local shell/manual reference smoke, not a real board flow. |
| Real EXM-K target smoke | Deferred | No VM, board credentials, CANSim, ZMQ, or target automation is required for automated readiness. |
| CANSim, target automation, `agent_task`, `python` recipes, `--jobs` | Deferred | Planned after SSH/SCP and run history are stable. |
| Git status, commits, tags | Not readiness criteria | Product readiness is proven by deterministic CLI tests and smoke commands. |

## Development Verification

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m compileall -q src tests
```
