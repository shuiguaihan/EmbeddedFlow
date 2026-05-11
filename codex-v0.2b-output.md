Implemented `CODEX-TASK-v0.2b.md` end to end.

What changed:
- Added `agent_task`, `python` plugin executor, and `test_design_v1` schema validation.
- Added `ef satisfy --jobs N`, `ef evidence compact`, and enhanced `ef recipe complete` for agent task artifact validation/copying.
- Added requested tests plus an extra integration test for schema validation on `recipe complete`.
- Updated README support matrix/plugin docs and bumped version to `0.3.0`.

Verification:
- Baseline before changes: 16 existing tests passed.
- Final suite: `33 tests` passed.
- `compileall` passed.
- CLI help checks passed for root, `satisfy --help`, and `evidence compact --help`.
- EXM-K DAG/dry-run and demo dry-run backward compatibility checks passed.