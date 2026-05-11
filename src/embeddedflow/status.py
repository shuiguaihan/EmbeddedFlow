from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .evidence import EvidenceStore
from .hashing import compute_recipe_hash, compute_source_hash
from .models import EvidenceEvent, Graph, Recipe, Requirement


@dataclass(slots=True)
class NodeStatus:
    node: str
    status: str
    reason: str
    latest: EvidenceEvent | None = None
    source_hash: str | None = None
    recipe_hash: str | None = None

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {"status": self.status, "reason": self.reason}
        if self.latest is not None:
            data["latest_event"] = self.latest.event
            data["latest_ts"] = self.latest.ts
        if self.source_hash is not None:
            data["source_hash"] = self.source_hash
        if self.recipe_hash is not None:
            data["recipe_hash"] = self.recipe_hash
        return data


def node_watch(requirement: Requirement, recipe: Recipe) -> list[str]:
    return recipe.watch or requirement.watch


def current_hashes(root: Path, requirement: Requirement, recipe: Recipe) -> tuple[str, str]:
    source_hash = compute_source_hash(node_watch(requirement, recipe), root)
    recipe_hash = compute_recipe_hash(Path(recipe.path)) if recipe.path else ""
    return source_hash, recipe_hash


def _status_for(
    node: str,
    root: Path,
    requirement: Requirement,
    graph: Graph,
    store: EvidenceStore,
    memo: dict[str, NodeStatus],
    visiting: set[str],
) -> NodeStatus:
    if node in memo:
        return memo[node]
    if node in visiting:
        return NodeStatus(node=node, status="failed", reason="cycle during status evaluation")
    visiting.add(node)
    recipe = graph.nodes[node]
    dep_statuses = [_status_for(dep, root, requirement, graph, store, memo, visiting) for dep in graph.reverse_edges[node]]
    visiting.remove(node)
    latest = store.latest_event(node, requirement.id)
    source_hash, recipe_hash = current_hashes(root, requirement, recipe)

    if latest is None:
        result = NodeStatus(node=node, status="missing", reason="no produced evidence", source_hash=source_hash, recipe_hash=recipe_hash)
    elif latest.event == "invalidated":
        result = NodeStatus(node=node, status="stale", reason=latest.reason or "invalidated", latest=latest, source_hash=source_hash, recipe_hash=recipe_hash)
    elif latest.event == "failed" or latest.status == "fail":
        result = NodeStatus(node=node, status="failed", reason=latest.error or "latest execution failed", latest=latest, source_hash=source_hash, recipe_hash=recipe_hash)
    elif any(dep.status != "valid" for dep in dep_statuses):
        result = NodeStatus(node=node, status="stale", reason="dependency invalid", latest=latest, source_hash=source_hash, recipe_hash=recipe_hash)
    elif latest.status != "pass":
        result = NodeStatus(node=node, status="failed", reason="latest evidence is not pass", latest=latest, source_hash=source_hash, recipe_hash=recipe_hash)
    elif latest.source_hash is not None and latest.source_hash != source_hash:
        result = NodeStatus(node=node, status="stale", reason="source_changed", latest=latest, source_hash=source_hash, recipe_hash=recipe_hash)
    elif latest.recipe_hash is not None and latest.recipe_hash != recipe_hash:
        result = NodeStatus(node=node, status="stale", reason="recipe_changed", latest=latest, source_hash=source_hash, recipe_hash=recipe_hash)
    elif recipe.review == "required":
        review = store.latest_review(node, requirement.id, after_ts=latest.ts)
        if review is None:
            result = NodeStatus(node=node, status="pending_review", reason="review required", latest=latest, source_hash=source_hash, recipe_hash=recipe_hash)
        elif review.review_status == "accepted":
            result = NodeStatus(node=node, status="valid", reason="review accepted", latest=latest, source_hash=source_hash, recipe_hash=recipe_hash)
        elif review.review_status == "rejected":
            result = NodeStatus(node=node, status="rejected", reason=review.rationale or "review rejected", latest=latest, source_hash=source_hash, recipe_hash=recipe_hash)
        else:
            result = NodeStatus(node=node, status="pending_review", reason="conditional review", latest=latest, source_hash=source_hash, recipe_hash=recipe_hash)
    else:
        result = NodeStatus(node=node, status="valid", reason="evidence current", latest=latest, source_hash=source_hash, recipe_hash=recipe_hash)
    memo[node] = result
    return result


def evaluate_status(root: Path, requirement: Requirement, graph: Graph, store: EvidenceStore) -> dict[str, NodeStatus]:
    memo: dict[str, NodeStatus] = {}
    for node in graph.nodes:
        _status_for(node, root, requirement, graph, store, memo, set())
    return {node: memo[node] for node in sorted(memo)}


def requirement_satisfied(statuses: dict[str, NodeStatus], requirement: Requirement) -> bool:
    return all(statuses[node].status == "valid" for node in requirement.evidence)
