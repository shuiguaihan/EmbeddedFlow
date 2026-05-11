from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import Recipe, Requirement
from .yaml_compat import safe_load


class LoadError(ValueError):
    pass


def _read_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise LoadError(f"missing file: {path}")
    data = safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise LoadError(f"YAML root must be a mapping: {path}")
    return data


def _string_list(data: Any, field: str, *, required: bool = False) -> list[str]:
    if data is None:
        if required:
            raise LoadError(f"missing required list: {field}")
        return []
    if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
        raise LoadError(f"{field} must be a list of strings")
    return list(data)


def load_requirement(root: Path, req_id: str) -> Requirement:
    path = root / ".ef" / "requirements" / f"{req_id}.yaml"
    data = _read_mapping(path)
    rid = data.get("id")
    title = data.get("title")
    if not isinstance(rid, str) or not rid:
        raise LoadError(f"requirement id missing or invalid: {path}")
    if rid != req_id:
        raise LoadError(f"requirement id mismatch: expected {req_id}, got {rid}")
    if not isinstance(title, str) or not title:
        raise LoadError(f"requirement title missing or invalid: {path}")
    evidence = _string_list(data.get("evidence"), "evidence", required=True)
    if not evidence:
        raise LoadError(f"requirement evidence cannot be empty: {path}")
    return Requirement(
        id=rid,
        title=title,
        evidence=evidence,
        watch=_string_list(data.get("watch"), "watch"),
        source=data.get("source") if isinstance(data.get("source"), str) else None,
        scope=data.get("scope") if isinstance(data.get("scope"), str) else None,
        tags=_string_list(data.get("tags"), "tags"),
        raw=data,
    )


def load_recipe(root: Path, recipe_id: str) -> Recipe:
    path = root / ".ef" / "recipes" / f"{recipe_id}.yaml"
    data = _read_mapping(path)
    rid = data.get("id")
    rtype = data.get("type")
    description = data.get("description")
    if rid != recipe_id:
        raise LoadError(f"recipe id mismatch: expected {recipe_id}, got {rid!r}")
    if not isinstance(rtype, str) or not rtype:
        raise LoadError(f"recipe type missing or invalid: {path}")
    if not isinstance(description, str) or not description:
        raise LoadError(f"recipe description missing or invalid: {path}")
    produces = data.get("produces") or []
    if not isinstance(produces, list):
        raise LoadError(f"produces must be a list: {path}")
    steps = data.get("steps") or []
    if not isinstance(steps, list) or not all(isinstance(step, dict) for step in steps):
        raise LoadError(f"steps must be a list of mappings: {path}")
    timeout = data.get("timeout", 300)
    if not isinstance(timeout, int):
        raise LoadError(f"timeout must be an integer: {path}")
    return Recipe(
        id=rid,
        type=rtype,
        description=description,
        depends_on=_string_list(data.get("depends_on"), "depends_on"),
        watch=_string_list(data.get("watch"), "watch"),
        review=data.get("review") if isinstance(data.get("review"), str) else None,
        command=data.get("command") if isinstance(data.get("command"), str) else None,
        working_dir=data.get("working_dir") if isinstance(data.get("working_dir"), str) else None,
        env=data.get("env") if isinstance(data.get("env"), dict) else {},
        produces=produces,
        steps=steps,
        timeout=timeout,
        remote=bool(data.get("remote", False)),
        target=data.get("target") if isinstance(data.get("target"), str) else "default",
        instructions=data.get("instructions") if isinstance(data.get("instructions"), str) else None,
        path=str(path),
        raw=data,
    )


def load_recipes_for_requirement(root: Path, requirement: Requirement) -> dict[str, Recipe]:
    recipes: dict[str, Recipe] = {}

    def visit(recipe_id: str) -> None:
        if recipe_id in recipes:
            return
        recipe = load_recipe(root, recipe_id)
        recipes[recipe_id] = recipe
        for dep in recipe.depends_on:
            visit(dep)

    for evidence_id in requirement.evidence:
        visit(evidence_id)
    return recipes
