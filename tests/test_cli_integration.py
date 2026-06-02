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


def write_project(root: Path):
    run_ef(root, "init", "--profile", "demo")
    src = root / "src"
    src.mkdir(exist_ok=True)
    (src / "app.txt").write_text("v1\n")
    req_dir = root / ".ef" / "requirements"
    recipe_dir = root / ".ef" / "recipes"
    (req_dir / "REQ-1.yaml").write_text(textwrap.dedent("""
        id: REQ-1
        title: Demo requirement
        evidence:
          - deploy
          - human_review.final
        watch:
          - src/**/*.txt
    """).strip() + "\n")
    (recipe_dir / "build.yaml").write_text(textwrap.dedent("""
        id: build
        type: shell
        description: Build demo artifact
        depends_on: []
        watch:
          - src/**/*.txt
        command: |
          mkdir -p out
          cat src/app.txt > out/app.txt
        produces:
          - artifact: out/app.txt
            type: text
            label: app
        timeout: 10
    """).strip() + "\n")
    (recipe_dir / "deploy.yaml").write_text(textwrap.dedent("""
        id: deploy
        type: shell
        description: Deploy demo artifact
        depends_on: [build]
        command: |
          mkdir -p deployed
          cp out/app.txt deployed/app.txt
        produces:
          - artifact: deployed/app.txt
            type: text
            label: deployed
        timeout: 10
    """).strip() + "\n")
    (recipe_dir / "human_review.final.yaml").write_text(textwrap.dedent("""
        id: human_review.final
        type: manual
        description: Final human acceptance
        depends_on: [deploy]
        review: required
        instructions: Review deployed/app.txt and accept when correct.
    """).strip() + "\n")


class CliIntegrationTests(unittest.TestCase):
    def test_init_creates_expected_project_structure_and_gitignore_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_ef(root, "init", "--profile", "demo")
            self.assertTrue((root / ".ef" / "requirements").is_dir())
            self.assertTrue((root / ".ef" / "recipes").is_dir())
            self.assertTrue((root / ".ef" / "profiles" / "demo" / "profile.yaml").is_file())
            gitignore = (root / ".gitignore").read_text()
            self.assertIn(".ef/evidence.jsonl", gitignore)
            self.assertIn(".ef/artifacts/", gitignore)

    def test_dag_status_satisfy_review_context_and_incremental_stale_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_project(root)

            status = json.loads(run_ef(root, "status", "REQ-1", "--format", "json").stdout)
            self.assertEqual(status["nodes"]["build"]["status"], "missing")
            self.assertEqual(status["nodes"]["deploy"]["status"], "missing")

            dag = json.loads(run_ef(root, "dag", "REQ-1", "--format", "json").stdout)
            self.assertEqual(dag["levels"], [["build"], ["deploy"], ["human_review.final"]])

            dry = run_ef(root, "satisfy", "REQ-1", "--dry-run").stdout
            self.assertIn("[run]   build", dry)
            self.assertIn("[run]   deploy", dry)

            run_ef(root, "satisfy", "REQ-1")
            pending = json.loads(run_ef(root, "status", "REQ-1", "--format", "json").stdout)
            self.assertEqual(pending["nodes"]["build"]["status"], "valid")
            self.assertEqual(pending["nodes"]["deploy"]["status"], "valid")
            self.assertEqual(pending["nodes"]["human_review.final"]["status"], "pending_review")

            run_ef(root, "review", "human_review.final", "REQ-1", "--accept", "--reviewer", "qa", "--rationale", "artifact checked")
            accepted = json.loads(run_ef(root, "status", "REQ-1", "--format", "json").stdout)
            self.assertEqual(accepted["nodes"]["human_review.final"]["status"], "valid")

            context = json.loads(run_ef(root, "context", "REQ-1", "--need", "deploy", "--format", "json").stdout)
            self.assertEqual(context["requirement"]["id"], "REQ-1")
            self.assertEqual(context["need"], "deploy")
            self.assertIn("build", context["dependencies"])

            (root / "src" / "app.txt").write_text("v2\n")
            stale = json.loads(run_ef(root, "status", "REQ-1", "--format", "json").stdout)
            self.assertEqual(stale["nodes"]["build"]["status"], "stale")
            self.assertEqual(stale["nodes"]["deploy"]["status"], "stale")
            self.assertEqual(stale["nodes"]["human_review.final"]["status"], "stale")

            events = json.loads(run_ef(root, "evidence", "list", "REQ-1", "--format", "json").stdout)
            self.assertGreaterEqual(len(events["events"]), 4)

    def test_evidence_invalidate_and_recipe_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_project(root)
            artifact = root / "external.txt"
            artifact.write_text("external\n")
            run_ef(root, "recipe", "complete", "build", "REQ-1", "--artifact", str(artifact), "--status", "pass")
            shown = json.loads(run_ef(root, "evidence", "show", "build", "REQ-1", "--format", "json").stdout)
            self.assertEqual(shown["latest"]["event"], "produced")
            run_ef(root, "evidence", "invalidate", "build", "REQ-1", "--reason", "manual")
            invalidated = json.loads(run_ef(root, "evidence", "show", "build", "REQ-1", "--format", "json").stdout)
            self.assertEqual(invalidated["latest"]["event"], "invalidated")

    def test_evidence_compact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_project(root)
            evidence_path = root / ".ef" / "evidence.jsonl"
            events = [
                {"ts": "2026-01-01T00:00:00Z", "event": "produced", "node": "build", "req": "REQ-1", "run": "run-1", "status": "pass"},
                {"ts": "2026-01-01T00:01:00Z", "event": "reviewed", "node": "build", "req": "REQ-1", "run": "run-1", "review_status": "accepted"},
                {"ts": "2026-01-01T00:02:00Z", "event": "produced", "node": "build", "req": "REQ-1", "run": "run-2", "status": "pass"},
                {"ts": "2026-01-01T00:03:00Z", "event": "reviewed", "node": "build", "req": "REQ-1", "run": "run-2", "review_status": "accepted"},
                {"ts": "2026-01-01T00:04:00Z", "event": "invalidated", "node": "build", "req": "REQ-1", "run": "run-3", "reason": "manual"},
            ]
            evidence_path.write_text("\n".join(json.dumps(event) for event in events) + "\n")

            result = run_ef(root, "evidence", "compact").stdout
            self.assertIn("Compacted 5 events to 3", result)
            compacted = [json.loads(line) for line in evidence_path.read_text().splitlines() if line.strip()]
            self.assertEqual([event["run"] for event in compacted], ["run-2", "run-2", "run-3"])

    def test_evidence_compact_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_project(root)
            evidence_path = root / ".ef" / "evidence.jsonl"
            original = "\n".join([
                json.dumps({"ts": "2026-01-01T00:00:00Z", "event": "produced", "node": "build", "req": "REQ-1", "run": "run-1", "status": "pass"}),
                json.dumps({"ts": "2026-01-01T00:01:00Z", "event": "produced", "node": "build", "req": "REQ-1", "run": "run-2", "status": "pass"}),
            ]) + "\n"
            evidence_path.write_text(original)

            result = run_ef(root, "evidence", "compact", "--dry-run").stdout
            self.assertIn("Would compact 2 events to 1", result)
            self.assertEqual(evidence_path.read_text(), original)

    def test_recipe_complete_validates_agent_task_artifact_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_ef(root, "init", "--profile", "demo")
            req_dir = root / ".ef" / "requirements"
            recipe_dir = root / ".ef" / "recipes"
            (req_dir / "REQ-A.yaml").write_text(textwrap.dedent("""
                id: REQ-A
                title: Agent task requirement
                evidence:
                  - test_design
            """).strip() + "\n")
            (recipe_dir / "test_design.yaml").write_text(textwrap.dedent("""
                id: test_design
                type: agent_task
                description: Generate test design
                agent_task:
                  context_query: "ef context {{req.id}} --need test_design --format json"
                  instructions: "Write a test design"
                  output_schema: test_design_v1
            """).strip() + "\n")

            invalid = root / "invalid.yaml"
            invalid.write_text("schema: test_design_v1\nrequirement: REQ-A\n")
            failed = run_ef(root, "recipe", "complete", "test_design", "REQ-A", "--artifact", str(invalid), check=False)
            self.assertNotEqual(failed.returncode, 0)
            shown = json.loads(run_ef(root, "evidence", "show", "test_design", "REQ-A", "--format", "json").stdout)
            self.assertEqual(shown["latest"]["event"], "failed")
            self.assertIn("missing required key: stimulus", shown["latest"]["error"])

            valid = root / "valid.yaml"
            valid.write_text(textwrap.dedent("""
                schema: test_design_v1
                requirement: REQ-A
                stimulus:
                  type: manual
                observations:
                  - id: visual
                    type: visual
                pass_criteria:
                  - id: checked
                    type: manual
                automation_plan:
                  automated: []
                  manual: []
            """).strip() + "\n")
            run_ef(root, "recipe", "complete", "test_design", "REQ-A", "--artifact", str(valid))
            shown = json.loads(run_ef(root, "evidence", "show", "test_design", "REQ-A", "--format", "json").stdout)
            self.assertEqual(shown["latest"]["event"], "produced")
            copied = root / ".ef" / "artifacts" / "REQ-A" / "test_design" / "valid.yaml"
            self.assertTrue(copied.is_file())


class AdditionalCliTests(unittest.TestCase):
    def test_profile_list_recipe_list_and_direct_recipe_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_project(root)
            profiles = run_ef(root, "profile", "list").stdout
            self.assertIn("demo", profiles)
            recipes = run_ef(root, "recipe", "list", "--type", "shell").stdout
            self.assertIn("build", recipes)
            self.assertIn("deploy", recipes)
            self.assertNotIn("human_review.final", recipes)
            run_ef(root, "recipe", "run", "build", "REQ-1", "--force")
            shown = json.loads(run_ef(root, "evidence", "show", "build", "REQ-1", "--format", "json").stdout)
            self.assertEqual(shown["latest"]["event"], "produced")
            self.assertEqual(shown["latest"]["status"], "pass")

    def test_remote_shell_recipe_requires_connection_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_ef(root, "init", "--profile", "demo")
            req_dir = root / ".ef" / "requirements"
            recipe_dir = root / ".ef" / "recipes"
            (req_dir / "REQ-REMOTE.yaml").write_text(textwrap.dedent("""
                id: REQ-REMOTE
                title: Remote recipe boundary
                evidence:
                  - remote_build
            """).strip() + "\n")
            (recipe_dir / "remote_build.yaml").write_text(textwrap.dedent("""
                id: remote_build
                type: shell
                description: Remote build
                target: vm
                remote: true
                command: echo should-not-run
            """).strip() + "\n")

            proc = run_ef(root, "satisfy", "REQ-REMOTE", check=False)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("no connection config for target: vm", proc.stderr)

            evidence_path = root / ".ef" / "evidence.jsonl"
            if evidence_path.exists():
                events = [json.loads(line) for line in evidence_path.read_text().splitlines() if line.strip()]
            else:
                events = []
            self.assertFalse(any(
                event.get("event") == "produced"
                and event.get("node") == "remote_build"
                and event.get("status") == "pass"
                for event in events
            ))

    def test_multi_step_shell_recipe_records_evidence_and_step_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_ef(root, "init", "--profile", "demo")
            req_dir = root / ".ef" / "requirements"
            recipe_dir = root / ".ef" / "recipes"
            (req_dir / "REQ-STEPS.yaml").write_text(textwrap.dedent("""
                id: REQ-STEPS
                title: Step recipe
                evidence:
                  - stepped
            """).strip() + "\n")
            (recipe_dir / "stepped.yaml").write_text(textwrap.dedent("""
                id: stepped
                type: shell
                description: Multi-step local recipe
                steps:
                  - name: step1
                    command: echo hello
                  - name: step2
                    command: echo world
                timeout: 10
            """).strip() + "\n")

            run_ef(root, "satisfy", "REQ-STEPS")
            shown = json.loads(run_ef(root, "evidence", "show", "stepped", "REQ-STEPS", "--format", "json").stdout)
            self.assertEqual(shown["latest"]["event"], "produced")
            self.assertEqual(shown["latest"]["status"], "pass")
            step1_log = root / ".ef" / "artifacts" / "REQ-STEPS" / "stepped" / "step_step1.log"
            step2_log = root / ".ef" / "artifacts" / "REQ-STEPS" / "stepped" / "step_step2.log"
            self.assertIn("hello", step1_log.read_text())
            self.assertIn("world", step2_log.read_text())

    def test_run_list_and_show_display_recorded_run_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_project(root)
            run_ef(root, "satisfy", "REQ-1")
            evidence_path = root / ".ef" / "evidence.jsonl"
            events = [json.loads(line) for line in evidence_path.read_text().splitlines() if line.strip()]
            run_id = next(event["run"] for event in events if event.get("node") == "build")

            listed = run_ef(root, "run", "list").stdout
            self.assertIn(run_id, listed)
            self.assertIn("REQ-1", listed)
            shown = run_ef(root, "run", "show", run_id).stdout
            self.assertIn("build", shown)
            self.assertIn("deploy", shown)

    def test_review_accept_requires_rationale_before_gate_becomes_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_project(root)

            run_ef(root, "satisfy", "REQ-1")
            pending = json.loads(run_ef(root, "status", "REQ-1", "--format", "json").stdout)
            self.assertEqual(pending["nodes"]["human_review.final"]["status"], "pending_review")

            rejected = run_ef(root, "review", "human_review.final", "REQ-1", "--accept", check=False)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("--accept requires --rationale", rejected.stderr)

            run_ef(root, "review", "human_review.final", "REQ-1", "--accept", "--reviewer", "qa", "--rationale", "artifact checked")
            accepted = json.loads(run_ef(root, "status", "REQ-1", "--format", "json").stdout)
            self.assertEqual(accepted["nodes"]["human_review.final"]["status"], "valid")

    def test_exm_k_reference_is_simulated_local_smoke(self):
        root = REPO_ROOT / "examples" / "exm-k"
        dag = json.loads(run_ef(root, "dag", "REQ-EXM-FUEL-GAUGE-001", "--format", "json").stdout)
        self.assertEqual(dag["levels"], [["test_design"], ["build"], ["deploy"], ["human_review.final"]])

        dry = run_ef(root, "satisfy", "REQ-EXM-FUEL-GAUGE-001", "--dry-run").stdout
        for node in ["test_design", "build", "deploy", "human_review.final"]:
            self.assertIn(f"[run]   {node}", dry)
        for forbidden in ["ssh", "VM", "board credentials", "CANSim", "ZMQ"]:
            self.assertNotIn(forbidden, dry)

        recipes = sorted((root / ".ef" / "recipes").glob("*.yaml"))
        self.assertTrue(recipes)
        for recipe in recipes:
            self.assertNotIn("remote:", recipe.read_text())
        self.assertIn("review: required", (root / ".ef" / "recipes" / "test_design.yaml").read_text())
        self.assertIn("review: required", (root / ".ef" / "recipes" / "human_review.final.yaml").read_text())


class DocumentationBoundaryTests(unittest.TestCase):
    def test_design_docs_do_not_present_deferred_target_flow_as_v0_3_acceptance(self):
        docs = "\n".join([
            (REPO_ROOT / "DESIGN-evidence-dag.md").read_text(encoding="utf-8"),
            (REPO_ROOT / "DESIGN-evidence-dag-zh.md").read_text(encoding="utf-8"),
        ])
        forbidden_current_examples = [
            "--profile exm-k",
            "remote:vm",
            "remote:board",
            "cross-compiling on VM",
            "deploying to board",
            "capturing screenshots",
            "collecting board log",
            "VM 上交叉编译",
            "部署到板端中",
            "注入 CAN 信号中",
            "截图捕获中",
            "采集板端日志中",
            "--format yaml",
        ]
        for phrase in forbidden_current_examples:
            self.assertNotIn(phrase, docs)
        self.assertIn("v0.3.0 is an Evidence-DAG workflow prototype release", docs)
        self.assertIn("not a real target-device automation release", docs)
        self.assertIn("Remote shell execution is supported in v0.3.0", docs)
        self.assertIn("Multi-step shell recipes and SCP steps are supported in v0.3.0", docs)
        self.assertIn("not v0.3.0 release acceptance examples", docs)
        self.assertIn("production-board profile shape is retained as real-target roadmap material", docs)
        self.assertIn("v0.3.0 Release 状态边界", docs)
        self.assertIn("真实 EXM-K target smoke", docs)
        self.assertIn("多步骤 shell recipe 和 SCP step", docs)


if __name__ == "__main__":
    unittest.main()
