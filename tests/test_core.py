import json
import tempfile
import unittest
from pathlib import Path


class TemplateAndHashTests(unittest.TestCase):
    def test_template_resolves_nested_values_and_rejects_missing_keys(self):
        from embeddedflow.template import TemplateError, render_template

        data = {"profile": {"build": {"artifact_path": "build/app"}}, "vars": {"jobs": 4}}
        self.assertEqual(render_template("artifact={{profile.build.artifact_path}}", data), "artifact=build/app")
        self.assertEqual(render_template("{{vars.jobs}}", data), "4")
        with self.assertRaises(TemplateError):
            render_template("{{profile.missing.value}}", data)

    def test_hashing_is_deterministic_and_detects_path_or_content_changes(self):
        from embeddedflow.hashing import compute_recipe_hash, compute_source_hash

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            src.mkdir()
            (src / "a.c").write_text("int a = 1;\n")
            first = compute_source_hash(["src/**/*.c"], root)
            self.assertEqual(first, compute_source_hash(["src/**/*.c"], root))
            (src / "a.c").write_text("int a = 2;\n")
            self.assertNotEqual(first, compute_source_hash(["src/**/*.c"], root))

            recipe = root / "recipe.yaml"
            recipe.write_text("# comment\nid: build\ntype: shell\ndepends_on: []\n")
            with_comment = compute_recipe_hash(recipe)
            recipe.write_text("type: shell\ndepends_on: []\nid: build\n")
            self.assertEqual(with_comment, compute_recipe_hash(recipe))


class EvidenceStoreTests(unittest.TestCase):
    def test_jsonl_store_appends_filters_latest_and_reviews(self):
        from embeddedflow.evidence import EvidenceEvent, EvidenceStore

        with tempfile.TemporaryDirectory() as tmp:
            store = EvidenceStore(Path(tmp) / ".ef" / "evidence.jsonl")
            store.append(EvidenceEvent(event="produced", node="build", req="REQ-1", run="run-1", status="pass"))
            store.append(EvidenceEvent(event="reviewed", node="build", req="REQ-1", run="run-1", review_status="accepted", rationale="verified"))
            store.append(EvidenceEvent(event="invalidated", node="build", req="REQ-1", run="run-2", reason="manual"))

            self.assertEqual(len(store.list_events(req="REQ-1")), 3)
            self.assertEqual(store.latest_event("build", "REQ-1").event, "invalidated")
            self.assertEqual(store.latest_review("build", "REQ-1").review_status, "accepted")
            self.assertEqual(store.list_events(req="REQ-404"), [])


class DagTests(unittest.TestCase):
    def test_graph_includes_transitive_dependencies_and_topological_levels(self):
        from embeddedflow.dag import build_graph, topological_levels
        from embeddedflow.models import Recipe, Requirement

        req = Requirement(id="REQ-1", title="demo", evidence=["deploy"], watch=[])
        recipes = {
            "build": Recipe(id="build", type="shell", description="build", depends_on=[]),
            "deploy": Recipe(id="deploy", type="shell", description="deploy", depends_on=["build"]),
        }
        graph = build_graph(req, recipes)
        self.assertEqual(set(graph.nodes), {"build", "deploy"})
        self.assertEqual(graph.edges, {"build": ["deploy"], "deploy": []})
        self.assertEqual(topological_levels(graph), [["build"], ["deploy"]])

    def test_graph_rejects_missing_recipes_and_cycles(self):
        from embeddedflow.dag import DagError, build_graph
        from embeddedflow.models import Recipe, Requirement

        with self.assertRaises(DagError):
            build_graph(Requirement(id="REQ", title="x", evidence=["missing"], watch=[]), {})

        recipes = {
            "a": Recipe(id="a", type="shell", description="a", depends_on=["b"]),
            "b": Recipe(id="b", type="shell", description="b", depends_on=["a"]),
        }
        with self.assertRaises(DagError):
            build_graph(Requirement(id="REQ", title="x", evidence=["a"], watch=[]), recipes)


class ConfigTests(unittest.TestCase):
    def test_resolve_connection_returns_ssh_connection_and_rejects_missing_target(self):
        from embeddedflow.config import ConfigError, resolve_connection

        config = {
            "local_env": {
                "targets": {
                    "vm": {
                        "host": "192.0.2.10",
                        "port": 2202,
                        "user": "builder",
                        "auth_mode": "key",
                        "key_path": "/tmp/id_ed25519",
                    }
                }
            }
        }
        conn = resolve_connection(config, "vm")
        self.assertEqual(conn.host, "192.0.2.10")
        self.assertEqual(conn.port, 2202)
        self.assertEqual(conn.user, "builder")
        self.assertEqual(conn.auth_mode, "key")
        self.assertEqual(conn.key_path, "/tmp/id_ed25519")

        with self.assertRaises(ConfigError):
            resolve_connection(config, "board")


if __name__ == "__main__":
    unittest.main()
