from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

from .context import build_context
from .dag import build_graph, downstream_nodes, topological_levels
from .evidence import EvidenceEvent, EvidenceStore
from .executors.manual import execute_manual
from .executors.shell import execute_shell
from .config import load_project_config
from .loaders import load_recipes_for_requirement, load_requirement, load_recipe
from .models import Graph, Recipe, Requirement
from .paths import ensure_structure, evidence_path, project_root
from .render import dump_data
from .status import current_hashes, evaluate_status, requirement_satisfied


class CliError(Exception):
    pass


def _load_workspace(req_id: str, root: Path | None = None) -> tuple[Path, Requirement, dict[str, Recipe], Graph, EvidenceStore]:
    root = project_root(root)
    requirement = load_requirement(root, req_id)
    recipes = load_recipes_for_requirement(root, requirement)
    graph = build_graph(requirement, recipes)
    store = EvidenceStore(evidence_path(root))
    return root, requirement, recipes, graph, store


def _status_payload(root: Path, req: Requirement, graph: Graph, store: EvidenceStore) -> dict[str, Any]:
    statuses = evaluate_status(root, req, graph, store)
    return {
        "requirement": req.id,
        "satisfied": requirement_satisfied(statuses, req),
        "nodes": {node: statuses[node].to_dict() for node in sorted(statuses)},
    }


def _print_status_text(payload: dict[str, Any]) -> None:
    print(f"Requirement {payload['requirement']} satisfied={str(payload['satisfied']).lower()}")
    for node, data in payload["nodes"].items():
        print(f"{node:24} {data['status']:15} {data['reason']}")


def cmd_init(args: argparse.Namespace) -> int:
    root = Path.cwd().resolve()
    ensure_structure(root, args.profile)
    print(f"Initialized EmbeddedFlow project at {root}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root, req, _recipes, graph, store = _load_workspace(args.req_id)
    payload = _status_payload(root, req, graph, store)
    if args.format == "json":
        print(dump_data(payload, "json"), end="")
    else:
        _print_status_text(payload)
    return 0


def cmd_dag(args: argparse.Namespace) -> int:
    root, req, _recipes, graph, store = _load_workspace(args.req_id)
    statuses = evaluate_status(root, req, graph, store)
    payload = {
        "requirement": req.id,
        "nodes": sorted(graph.nodes),
        "edges": graph.edges,
        "reverse_edges": graph.reverse_edges,
        "levels": topological_levels(graph),
        "statuses": {node: statuses[node].status for node in sorted(statuses)},
    }
    if args.format == "json":
        print(dump_data(payload, "json"), end="")
    else:
        for idx, level in enumerate(payload["levels"]):
            print(f"Level {idx}: " + ", ".join(f"{node}({statuses[node].status})" for node in level))
        for source, targets in graph.edges.items():
            for target in targets:
                print(f"{source} -> {target}")
    return 0


def _make_run_id() -> str:
    return time.strftime("ef-%Y%m%dT%H%M%S")


def _plan_actions(root: Path, req: Requirement, graph: Graph, store: EvidenceStore, force: str | None = None) -> list[tuple[str, str, str]]:
    statuses = evaluate_status(root, req, graph, store)
    forced = {force, *downstream_nodes(graph, force)} if force else set()
    actions: list[tuple[str, str, str]] = []
    for level in topological_levels(graph):
        for node in level:
            status = statuses[node].status
            if node in forced:
                actions.append(("run", node, "forced"))
            elif status == "valid":
                actions.append(("skip", node, statuses[node].reason))
            elif status == "pending_review":
                actions.append(("wait", node, statuses[node].reason))
            elif status == "rejected":
                actions.append(("run", node, "review rejected"))
            else:
                actions.append(("run", node, status))
    return actions


def _record_result(root: Path, req: Requirement, graph: Graph, store: EvidenceStore, run_id: str, node: str, result) -> None:
    recipe = graph.nodes[node]
    source_hash, recipe_hash = current_hashes(root, req, recipe)
    depends = []
    for dep in graph.reverse_edges[node]:
        latest = store.latest_event(dep, req.id)
        if latest and latest.recipe_hash:
            depends.append(f"{dep}@{latest.recipe_hash}")
    if result.status == "pass":
        store.append(
            EvidenceEvent(
                event="produced",
                node=node,
                req=req.id,
                run=run_id,
                recipe=node,
                status="pass",
                duration_s=round(result.duration_s, 3),
                artifacts=result.artifacts,
                source_hash=source_hash,
                recipe_hash=recipe_hash,
                depends=depends,
            )
        )
    else:
        store.append(
            EvidenceEvent(
                event="failed",
                node=node,
                req=req.id,
                run=run_id,
                recipe=node,
                status="fail",
                duration_s=round(result.duration_s, 3),
                artifacts=result.artifacts,
                source_hash=source_hash,
                recipe_hash=recipe_hash,
                exit_code=result.exit_code,
                error=result.error,
                stderr_tail=result.stderr_tail,
            )
        )


def _execute_recipe(root: Path, req: Requirement, recipe: Recipe):
    if recipe.type == "shell":
        config = load_project_config(root)
        return execute_shell(root, req.id, recipe, config)
    if recipe.type == "manual":
        return execute_manual(root, req.id, recipe)
    raise CliError(f"unsupported recipe type in v0.1: {recipe.type}")


def cmd_satisfy(args: argparse.Namespace) -> int:
    root, req, _recipes, graph, store = _load_workspace(args.req_id)
    actions = _plan_actions(root, req, graph, store, args.force)
    if args.dry_run:
        for action, node, reason in actions:
            print(f"[{action}]   {node:24} {reason}")
        return 0
    run_id = _make_run_id()
    for action, node, reason in actions:
        if action == "skip":
            print(f"[skip]  {node:24} {reason}")
            continue
        if action == "wait":
            print(f"[wait]  {node:24} {reason}")
            continue
        recipe = graph.nodes[node]
        print(f"[run]   {node:24} {reason}")
        result = _execute_recipe(root, req, recipe)
        _record_result(root, req, graph, store, run_id, node, result)
        if result.status != "pass" and not args.continue_on_error:
            print(f"[fail]  {node:24} {result.error or 'failed'}", file=sys.stderr)
            return result.exit_code or 1
        if recipe.review == "required":
            print(f"[wait]  {node:24} review required: ef review {node} {req.id} --accept --rationale <text>")
    statuses = evaluate_status(root, req, graph, store)
    if requirement_satisfied(statuses, req):
        print(f"All evidence up to date. {req.id} is satisfied.")
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    if args.accept and not args.rationale:
        raise CliError("--accept requires --rationale")
    if args.accept == args.reject:
        raise CliError("choose exactly one of --accept or --reject")
    root = project_root()
    store = EvidenceStore(evidence_path(root))
    status = "accepted" if args.accept else "rejected"
    store.append(
        EvidenceEvent(
            event="reviewed",
            node=args.node_id,
            req=args.req_id,
            run=_make_run_id(),
            reviewer=args.reviewer,
            review_status=status,
            rationale=args.rationale,
        )
    )
    print(f"Recorded review for {args.node_id} {args.req_id}: {status}")
    return 0


def cmd_context(args: argparse.Namespace) -> int:
    root, req, _recipes, graph, store = _load_workspace(args.req_id)
    if args.need and args.need not in graph.nodes:
        raise CliError(f"unknown node for --need: {args.need}")
    statuses = evaluate_status(root, req, graph, store)
    payload = build_context(root, req, graph, statuses, store, args.need)
    if args.format == "json":
        print(dump_data(payload, "json"), end="")
    else:
        print(f"# Context for {req.id}")
        print(dump_data(payload, "yaml"), end="")
    return 0


def cmd_what_next(args: argparse.Namespace) -> int:
    root, req, _recipes, graph, store = _load_workspace(args.req_id)
    statuses = evaluate_status(root, req, graph, store)
    if requirement_satisfied(statuses, req):
        print(f"{req.id} is satisfied. No next action required.")
        return 0
    for level in topological_levels(graph):
        for node in level:
            status = statuses[node].status
            if status in {"missing", "stale", "failed", "rejected"}:
                print(f"Run: ef satisfy {req.id}")
                print(f"Next node: {node} ({status}: {statuses[node].reason})")
                return 0
            if status == "pending_review":
                print(f"Run: ef review {node} {req.id} --accept --rationale <text>")
                return 0
    return 0


def cmd_evidence_list(args: argparse.Namespace) -> int:
    root = project_root()
    store = EvidenceStore(evidence_path(root))
    events = [event.to_dict() for event in store.list_events(req=args.req_id, node=args.node, status=args.status)]
    payload = {"events": events}
    if args.format == "json":
        print(dump_data(payload, "json"), end="")
    else:
        for event in events:
            print(f"{event.get('ts')} {event.get('event')} {event.get('req')} {event.get('node')} {event.get('status', '')}")
    return 0


def cmd_evidence_show(args: argparse.Namespace) -> int:
    root = project_root()
    store = EvidenceStore(evidence_path(root))
    latest = store.latest_event(args.node_id, args.req_id)
    events = [event.to_dict() for event in store.list_events(req=args.req_id, node=args.node_id)]
    payload = {"latest": latest.to_dict() if latest else None, "events": events}
    if args.format == "json":
        print(dump_data(payload, "json"), end="")
    else:
        print(dump_data(payload, "yaml"), end="")
    return 0


def cmd_evidence_invalidate(args: argparse.Namespace) -> int:
    root = project_root()
    store = EvidenceStore(evidence_path(root))
    store.append(EvidenceEvent(event="invalidated", node=args.node_id, req=args.req_id, run=_make_run_id(), reason=args.reason))
    print(f"Invalidated {args.node_id} for {args.req_id}: {args.reason}")
    return 0


def cmd_run_list(args: argparse.Namespace) -> int:
    root = project_root()
    store = EvidenceStore(evidence_path(root))
    grouped: dict[str, list[EvidenceEvent]] = {}
    for event in store.read_all():
        grouped.setdefault(event.run, []).append(event)
    rows = []
    for run_id, events in grouped.items():
        ordered = sorted(events, key=lambda event: event.ts)
        reqs = sorted({event.req for event in ordered})
        nodes = {event.node for event in ordered}
        passed = sum(1 for event in ordered if event.status == "pass")
        failed = sum(1 for event in ordered if event.status == "fail" or event.event == "failed")
        rows.append((ordered[0].ts, run_id, ",".join(reqs), len(nodes), passed, failed))
    rows.sort(reverse=True)
    for ts, run_id, req_id, node_count, passed, failed in rows[: args.limit]:
        print(f"{run_id:24} {ts:20} {req_id:24} nodes={node_count} pass={passed} fail={failed}")
    return 0


def cmd_run_show(args: argparse.Namespace) -> int:
    root = project_root()
    store = EvidenceStore(evidence_path(root))
    events = sorted(store.list_events(run=args.run_id), key=lambda event: event.ts)
    if args.format == "json":
        print(dump_data({"run": args.run_id, "events": [event.to_dict() for event in events]}, "json"), end="")
    else:
        for event in events:
            status = event.status or event.review_status or ""
            print(f"{event.ts:20} {event.event:12} {event.req:24} {event.node:24} {status}")
    return 0


def cmd_recipe_complete(args: argparse.Namespace) -> int:
    root = project_root()
    req = load_requirement(root, args.req_id)
    recipe = load_recipe(root, args.recipe_id)
    store = EvidenceStore(evidence_path(root))
    source_hash, recipe_hash = current_hashes(root, req, recipe)
    artifact = Path(args.artifact)
    artifact_text = str(artifact.relative_to(root)) if artifact.is_absolute() and artifact.is_relative_to(root) else str(artifact)
    event_name = "produced" if args.status == "pass" else "failed"
    store.append(
        EvidenceEvent(
            event=event_name,
            node=args.recipe_id,
            req=args.req_id,
            run=_make_run_id(),
            recipe=args.recipe_id,
            status=args.status,
            artifacts=[artifact_text],
            source_hash=source_hash,
            recipe_hash=recipe_hash,
        )
    )
    print(f"Recorded {args.status} evidence for {args.recipe_id} {args.req_id}")
    return 0


def cmd_recipe_list(args: argparse.Namespace) -> int:
    root = project_root()
    recipe_dir = root / ".ef" / "recipes"
    if not recipe_dir.exists():
        return 0
    for path in sorted(recipe_dir.glob("*.yaml")):
        recipe_id = path.name[:-5]
        recipe = load_recipe(root, recipe_id)
        if args.type and recipe.type != args.type:
            continue
        print(f"{recipe.id:24} {recipe.type:10} {recipe.description}")
    return 0


def cmd_recipe_run(args: argparse.Namespace) -> int:
    root, req, _recipes, graph, store = _load_workspace(args.req_id)
    if args.recipe_id not in graph.nodes:
        raise CliError(f"recipe {args.recipe_id} is not part of requirement {args.req_id}")
    run_id = _make_run_id()
    recipe = graph.nodes[args.recipe_id]
    result = _execute_recipe(root, req, recipe)
    _record_result(root, req, graph, store, run_id, args.recipe_id, result)
    if result.status != "pass":
        print(f"[fail]  {args.recipe_id:24} {result.error or 'failed'}", file=sys.stderr)
        return result.exit_code or 1
    print(f"[pass]  {args.recipe_id:24}")
    if recipe.review == "required":
        print(f"[wait]  {args.recipe_id:24} review required: ef review {args.recipe_id} {req.id} --accept --rationale <text>")
    return 0


def cmd_profile_list(args: argparse.Namespace) -> int:
    root = project_root()
    profile_dir = root / ".ef" / "profiles"
    if not profile_dir.exists():
        return 0
    for path in sorted(profile_dir.iterdir()):
        if path.is_dir():
            print(path.name)
    return 0


def cmd_profile_show(args: argparse.Namespace) -> int:
    root = project_root()
    config = load_project_config(root, args.profile_id)
    print(dump_data(config, "yaml"), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ef")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init")
    p.add_argument("--profile")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("status")
    p.add_argument("req_id")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("dag")
    p.add_argument("req_id")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.set_defaults(func=cmd_dag)

    p = sub.add_parser("satisfy")
    p.add_argument("req_id")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force")
    p.add_argument("--continue-on-error", action="store_true")
    p.set_defaults(func=cmd_satisfy)

    p = sub.add_parser("review")
    p.add_argument("node_id")
    p.add_argument("req_id")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--accept", action="store_true")
    group.add_argument("--reject", action="store_true")
    p.add_argument("--reviewer", default="unknown")
    p.add_argument("--rationale")
    p.set_defaults(func=cmd_review)

    p = sub.add_parser("context")
    p.add_argument("req_id")
    p.add_argument("--need")
    p.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p.set_defaults(func=cmd_context)

    p = sub.add_parser("what-next")
    p.add_argument("req_id")
    p.set_defaults(func=cmd_what_next)

    evidence = sub.add_parser("evidence")
    ev_sub = evidence.add_subparsers(dest="evidence_command", required=True)
    p = ev_sub.add_parser("list")
    p.add_argument("req_id", nargs="?")
    p.add_argument("--status", default="all")
    p.add_argument("--node")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.set_defaults(func=cmd_evidence_list)
    p = ev_sub.add_parser("show")
    p.add_argument("node_id")
    p.add_argument("req_id")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.set_defaults(func=cmd_evidence_show)
    p = ev_sub.add_parser("invalidate")
    p.add_argument("node_id")
    p.add_argument("req_id")
    p.add_argument("--reason", default="manual")
    p.set_defaults(func=cmd_evidence_invalidate)

    run = sub.add_parser("run")
    run_sub = run.add_subparsers(dest="run_command", required=True)
    p = run_sub.add_parser("list")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_run_list)
    p = run_sub.add_parser("show")
    p.add_argument("run_id")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.set_defaults(func=cmd_run_show)

    recipe = sub.add_parser("recipe")
    recipe_sub = recipe.add_subparsers(dest="recipe_command", required=True)
    p = recipe_sub.add_parser("list")
    p.add_argument("--type")
    p.set_defaults(func=cmd_recipe_list)
    p = recipe_sub.add_parser("run")
    p.add_argument("recipe_id")
    p.add_argument("req_id")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_recipe_run)
    p = recipe_sub.add_parser("complete")
    p.add_argument("recipe_id")
    p.add_argument("req_id")
    p.add_argument("--artifact", required=True)
    p.add_argument("--status", choices=["pass", "fail"], required=True)
    p.set_defaults(func=cmd_recipe_complete)

    profile = sub.add_parser("profile")
    profile_sub = profile.add_subparsers(dest="profile_command", required=True)
    p = profile_sub.add_parser("list")
    p.set_defaults(func=cmd_profile_list)
    p = profile_sub.add_parser("show")
    p.add_argument("profile_id")
    p.set_defaults(func=cmd_profile_show)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (CliError, ValueError, OSError) as exc:
        print(f"ef: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
