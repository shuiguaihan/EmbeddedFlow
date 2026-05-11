import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"


def run_ef(cwd: Path, *args: str, check: bool = True):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC_PATH)
    proc = subprocess.run(
        [sys.executable, "-m", "embeddedflow.cli", *args],
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and proc.returncode != 0:
        raise AssertionError(f"ef {' '.join(args)} failed\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def write_parallel_project(root: Path, *, failing: bool = False) -> None:
    run_ef(root, "init", "--profile", "demo")
    req_dir = root / ".ef" / "requirements"
    recipe_dir = root / ".ef" / "recipes"
    evidence = ["a", "b"] if not failing else ["a", "after"]
    (req_dir / "REQ-P.yaml").write_text(textwrap.dedent(f"""
        id: REQ-P
        title: Parallel requirement
        evidence: [{", ".join(evidence)}]
    """).strip() + "\n")
    (recipe_dir / "a.yaml").write_text(textwrap.dedent("""
        id: a
        type: shell
        description: A
        command: |
          mkdir -p out
          echo a > out/a.txt
        timeout: 10
    """).strip() + "\n")
    if failing:
        (recipe_dir / "after.yaml").write_text(textwrap.dedent("""
            id: after
            type: shell
            description: After failure
            depends_on: [a]
            command: |
              mkdir -p out
              echo after > out/after.txt
            timeout: 10
        """).strip() + "\n")
        (recipe_dir / "a.yaml").write_text(textwrap.dedent("""
            id: a
            type: shell
            description: A fails
            command: exit 3
            timeout: 10
        """).strip() + "\n")
    else:
        (recipe_dir / "b.yaml").write_text(textwrap.dedent("""
            id: b
            type: shell
            description: B
            command: |
              mkdir -p out
              echo b > out/b.txt
            timeout: 10
        """).strip() + "\n")


def produced_nodes(root: Path) -> list[str]:
    events = [json.loads(line) for line in (root / ".ef" / "evidence.jsonl").read_text().splitlines() if line.strip()]
    return [event["node"] for event in events if event.get("event") == "produced"]


class ParallelTests(unittest.TestCase):
    def test_parallel_satisfy_with_jobs_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_parallel_project(root)
            run_ef(root, "satisfy", "REQ-P", "--jobs", "2")
            self.assertEqual(sorted(produced_nodes(root)), ["a", "b"])

    def test_jobs_1_is_identical_to_sequential(self):
        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            root1 = Path(tmp1)
            root2 = Path(tmp2)
            write_parallel_project(root1)
            write_parallel_project(root2)
            run_ef(root1, "satisfy", "REQ-P")
            run_ef(root2, "satisfy", "REQ-P", "--jobs", "1")
            self.assertEqual(produced_nodes(root1), produced_nodes(root2))

    def test_parallel_with_failure_and_continue_on_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_parallel_project(root, failing=True)
            stopped = run_ef(root, "satisfy", "REQ-P", "--jobs", "2", check=False)
            self.assertEqual(stopped.returncode, 3)
            self.assertFalse((root / "out" / "after.txt").exists())

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_parallel_project(root, failing=True)
            continued = run_ef(root, "satisfy", "REQ-P", "--jobs", "2", "--continue-on-error", check=False)
            self.assertEqual(continued.returncode, 0)
            self.assertTrue((root / "out" / "after.txt").exists())


if __name__ == "__main__":
    unittest.main()
