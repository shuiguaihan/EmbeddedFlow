from __future__ import annotations

from collections import deque

from .models import Graph, Recipe, Requirement


class DagError(ValueError):
    pass


def build_graph(requirement: Requirement, recipes: dict[str, Recipe]) -> Graph:
    needed: dict[str, Recipe] = {}

    def visit(node: str, stack: list[str]) -> None:
        if node in stack:
            cycle = " -> ".join([*stack, node])
            raise DagError(f"cycle detected: {cycle}")
        if node in needed:
            return
        recipe = recipes.get(node)
        if recipe is None:
            raise DagError(f"missing recipe for evidence node: {node}")
        needed[node] = recipe
        for dep in recipe.depends_on:
            visit(dep, [*stack, node])

    for node in requirement.evidence:
        visit(node, [])

    edges = {node: [] for node in needed}
    reverse = {node: [] for node in needed}
    for node, recipe in needed.items():
        for dep in recipe.depends_on:
            if dep not in needed:
                raise DagError(f"missing transitive recipe for dependency: {dep}")
            edges[dep].append(node)
            reverse[node].append(dep)
    for mapping in (edges, reverse):
        for key in mapping:
            mapping[key] = sorted(mapping[key])
    graph = Graph(nodes=needed, edges=edges, reverse_edges=reverse, required=list(requirement.evidence))
    topological_levels(graph)  # validate cycles introduced by malformed input
    return graph


def topological_levels(graph: Graph) -> list[list[str]]:
    indegree = {node: len(graph.reverse_edges[node]) for node in graph.nodes}
    ready = deque(sorted(node for node, degree in indegree.items() if degree == 0))
    levels: list[list[str]] = []
    seen = 0
    while ready:
        level = list(ready)
        ready.clear()
        levels.append(level)
        for node in level:
            seen += 1
            for dependent in graph.edges[node]:
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    ready.append(dependent)
        ready = deque(sorted(ready))
    if seen != len(graph.nodes):
        unresolved = sorted(node for node, degree in indegree.items() if degree > 0)
        raise DagError(f"cycle detected among: {', '.join(unresolved)}")
    return levels


def downstream_nodes(graph: Graph, node: str) -> set[str]:
    result: set[str] = set()
    queue = deque([node])
    while queue:
        current = queue.popleft()
        for dependent in graph.edges.get(current, []):
            if dependent not in result:
                result.add(dependent)
                queue.append(dependent)
    return result


def upstream_nodes(graph: Graph, node: str) -> set[str]:
    result: set[str] = set()
    queue = deque([node])
    while queue:
        current = queue.popleft()
        for dep in graph.reverse_edges.get(current, []):
            if dep not in result:
                result.add(dep)
                queue.append(dep)
    return result
