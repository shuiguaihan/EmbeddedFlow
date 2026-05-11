Implemented v0.2a SSH remote execution support.

Changed:
- Added `SSHConnection`, recipe `steps`, and `target` parsing.
- Added config target resolution via `resolve_connection()`.
- Reworked [shell.py](D:/Monster_Liu/code/EmbeddedFlow/src/embeddedflow/executors/shell.py) for local shell, remote SSH, SCP pull/push, produced artifact pulls, step logs, retries, timeouts, and ignored step failures.
- Added `ef run list`, `ef run show`, and `ef profile show`.
- Updated tests for remote config failure, multi-step recipes, run history, and connection resolution.
- Updated README support matrix and bumped version to `0.2.0`.
- Added a small YAML compatibility layer so the requested `python3` launcher works even when PyYAML is missing in that environment.

Verification passed:
- `python3 -m unittest discover -s tests -v` passed: 16 tests.
- `python3 -m compileall -q src tests` passed.
- `python3 -m embeddedflow.cli --help` passed.
- `python3 -m embeddedflow.cli run --help` passed.
- EXM-K `dag --format json` passed.
- EXM-K `satisfy --dry-run` passed.

No real SSH connection was attempted in tests.