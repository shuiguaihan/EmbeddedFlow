import json
import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from embeddedflow.executors.agent_task import execute_agent_task
from embeddedflow.models import Recipe


def write_requirement(root: Path) -> None:
    req_dir = root / ".ef" / "requirements"
    req_dir.mkdir(parents=True)
    (req_dir / "REQ-1.yaml").write_text(textwrap.dedent("""
        id: REQ-1
        title: Demo requirement
        evidence:
          - test_design
        watch:
          - src/**/*.c
    """).strip() + "\n")


class AgentTaskTests(unittest.TestCase):
    def test_agent_task_executor_setup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_requirement(root)
            recipe = Recipe(
                id="test_design",
                type="agent_task",
                description="Generate test design",
                raw={
                    "agent_task": {
                        "context_query": "ef context {{req.id}} --need test_design --format json",
                        "instructions": "Design tests for {{req.id}}",
                        "output_path": ".ef/artifacts/{{req.id}}/test_design/test_design.yaml",
                    }
                },
            )
            completed = SimpleNamespace(returncode=0, stdout=json.dumps({"requirement": {"id": "REQ-1"}}), stderr="")
            with patch("embeddedflow.executors.agent_task.subprocess.run", return_value=completed) as run:
                result = execute_agent_task(root, "REQ-1", recipe, {"profile": {"target": "demo"}})

            self.assertEqual(result.status, "pass")
            run.assert_called_once()
            artifact_dir = root / ".ef" / "artifacts" / "REQ-1" / "test_design"
            self.assertIn("Design tests for REQ-1", (artifact_dir / "instructions.md").read_text())
            self.assertEqual(json.loads((artifact_dir / "context.json").read_text())["requirement"]["id"], "REQ-1")

    def test_agent_task_with_missing_context_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_requirement(root)
            recipe = Recipe(
                id="test_design",
                type="agent_task",
                description="Generate test design",
                raw={"agent_task": {"instructions": "Design tests"}},
            )
            result = execute_agent_task(root, "REQ-1", recipe, {})
            self.assertEqual(result.status, "fail")
            self.assertIn("context_query", result.error)

    def test_agent_task_template_rendering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_requirement(root)
            recipe = Recipe(
                id="test_design",
                type="agent_task",
                description="Generate test design",
                raw={
                    "agent_task": {
                        "context_query": "ef context {{req.id}} --format json",
                        "instructions": "Req={{req.id}} profile={{profile.name}}",
                    }
                },
            )
            completed = SimpleNamespace(returncode=0, stdout="{}", stderr="")
            with patch("embeddedflow.executors.agent_task.subprocess.run", return_value=completed):
                result = execute_agent_task(root, "REQ-1", recipe, {"profile": {"name": "demo"}})
            self.assertEqual(result.status, "pass")
            text = (root / ".ef" / "artifacts" / "REQ-1" / "test_design" / "instructions.md").read_text()
            self.assertIn("Req=REQ-1 profile=demo", text)


if __name__ == "__main__":
    unittest.main()
