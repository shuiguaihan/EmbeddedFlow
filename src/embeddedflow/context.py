from __future__ import annotations

from pathlib import Path

from .dag import upstream_nodes
from .evidence import EvidenceStore
from .models import Graph, Requirement
from .status import NodeStatus


def build_context(
    root: Path,
    requirement: Requirement,
    graph: Graph,
    statuses: dict[str, NodeStatus],
    store: EvidenceStore,
    need: str | None = None,
) -> dict[str, object]:
    nodes = sorted(graph.nodes)
    dependencies: list[str] = []
    if need:
        dependencies = sorted(upstream_nodes(graph, need))
        include = sorted(set(dependencies) | {need})
    else:
        include = nodes
    return {
        "requirement": {
            "id": requirement.id,
            "title": requirement.title,
            "source": requirement.source,
            "scope": requirement.scope,
            "evidence": requirement.evidence,
            "watch": requirement.watch,
            "tags": requirement.tags,
        },
        "need": need,
        "dependencies": dependencies,
        "nodes": {
            node: {
                "recipe": graph.nodes[node].raw,
                "status": statuses[node].to_dict(),
                "latest_evidence": store.latest_event(node, requirement.id).to_dict() if store.latest_event(node, requirement.id) else None,
            }
            for node in include
        },
        "artifacts_root": str((root / ".ef" / "artifacts" / requirement.id).relative_to(root)),
    }
