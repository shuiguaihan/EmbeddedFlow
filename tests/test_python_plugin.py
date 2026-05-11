import tempfile
import textwrap
import unittest
from pathlib import Path

from embeddedflow.executors.python_plugin import execute_python
from embeddedflow.models import Recipe


class PythonPluginTests(unittest.TestCase):
    def test_python_plugin_executor_with_valid_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin_dir = root / ".ef" / "plugins"
            plugin_dir.mkdir(parents=True)
            (plugin_dir / "test_plugin.py").write_text(textwrap.dedent("""
                def run(root, req_id, recipe, config):
                    return {"status": "pass", "artifacts": []}
            """))
            recipe = Recipe(id="test_plugin", type="python", description="plugin")
            result = execute_python(root, "REQ-1", recipe, {"profile": {"name": "demo"}})
            self.assertEqual(result.status, "pass")

    def test_python_plugin_with_missing_plugin_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipe = Recipe(id="missing", type="python", description="plugin")
            result = execute_python(root, "REQ-1", recipe, {})
            self.assertEqual(result.status, "fail")
            self.assertIn("plugin not found", result.error)

    def test_python_plugin_with_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin_dir = root / ".ef" / "plugins"
            plugin_dir.mkdir(parents=True)
            (plugin_dir / "boom.py").write_text(textwrap.dedent("""
                def run(root, req_id, recipe, config):
                    raise RuntimeError("boom")
            """))
            recipe = Recipe(id="boom", type="python", description="plugin")
            result = execute_python(root, "REQ-1", recipe, {})
            self.assertEqual(result.status, "fail")
            self.assertIn("boom", result.error)

    def test_python_plugin_with_invalid_return(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin_dir = root / ".ef" / "plugins"
            plugin_dir.mkdir(parents=True)
            (plugin_dir / "invalid.py").write_text(textwrap.dedent("""
                def run(root, req_id, recipe, config):
                    return "pass"
            """))
            recipe = Recipe(id="invalid", type="python", description="plugin")
            result = execute_python(root, "REQ-1", recipe, {})
            self.assertEqual(result.status, "fail")
            self.assertIn("non-dict", result.error)


if __name__ == "__main__":
    unittest.main()
