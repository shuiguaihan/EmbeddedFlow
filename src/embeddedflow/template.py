from __future__ import annotations

import re
from typing import Any

_TOKEN = re.compile(r"{{\s*([A-Za-z0-9_.-]+)\s*}}")


class TemplateError(ValueError):
    pass


def resolve_path(path: str, data: dict[str, Any]) -> Any:
    current: Any = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise TemplateError(f"unknown template variable: {path}")
    return current


def render_template(value: str, data: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        resolved = resolve_path(match.group(1), data)
        return str(resolved)

    return _TOKEN.sub(replace, value)


def render_value(value: Any, data: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return render_template(value, data)
    if isinstance(value, list):
        return [render_value(item, data) for item in value]
    if isinstance(value, dict):
        return {key: render_value(item, data) for key, item in value.items()}
    return value
