from __future__ import annotations

import json
from typing import Any

try:
    import yaml as _pyyaml
except ModuleNotFoundError:  # pragma: no cover - exercised only when PyYAML is absent
    _pyyaml = None


def safe_load(text: str) -> Any:
    if _pyyaml is not None:
        return _pyyaml.safe_load(text)
    return _parse_yaml_subset(text)


def safe_dump(data: Any, *, allow_unicode: bool = True, sort_keys: bool = False) -> str:
    if _pyyaml is not None:
        return _pyyaml.safe_dump(data, allow_unicode=allow_unicode, sort_keys=sort_keys)
    return json.dumps(data, ensure_ascii=not allow_unicode, indent=2, sort_keys=sort_keys) + "\n"


def _parse_yaml_subset(text: str) -> Any:
    lines = text.splitlines()
    parsed, _index = _parse_block(lines, 0, 0)
    return parsed


def _parse_block(lines: list[str], index: int, indent: int) -> tuple[Any, int]:
    index = _skip_empty(lines, index)
    if index >= len(lines):
        return {}, index
    current_indent = _indent_of(lines[index])
    if current_indent < indent:
        return {}, index
    if _content(lines[index]).startswith("- "):
        return _parse_list(lines, index, current_indent)
    return _parse_mapping(lines, index, current_indent)


def _parse_mapping(lines: list[str], index: int, indent: int) -> tuple[dict[str, Any], int]:
    data: dict[str, Any] = {}
    while index < len(lines):
        index = _skip_empty(lines, index)
        if index >= len(lines):
            break
        line_indent = _indent_of(lines[index])
        if line_indent < indent:
            break
        if line_indent > indent:
            break
        content = _content(lines[index])
        if content.startswith("- "):
            break
        key, value = _split_key_value(content)
        if value == "|":
            block, index = _parse_literal(lines, index + 1, indent + 2)
            data[key] = block
        elif value == "":
            child, index = _parse_block(lines, index + 1, indent + 2)
            data[key] = child
        else:
            data[key] = _parse_scalar(value)
            index += 1
    return data, index


def _parse_list(lines: list[str], index: int, indent: int) -> tuple[list[Any], int]:
    items: list[Any] = []
    while index < len(lines):
        index = _skip_empty(lines, index)
        if index >= len(lines):
            break
        line_indent = _indent_of(lines[index])
        if line_indent < indent:
            break
        if line_indent > indent:
            break
        content = _content(lines[index])
        if not content.startswith("- "):
            break
        item_text = content[2:].strip()
        index += 1
        if item_text == "":
            item, index = _parse_block(lines, index, indent + 2)
            items.append(item)
        elif ":" in item_text and not _looks_like_quoted(item_text):
            key, value = _split_key_value(item_text)
            item: dict[str, Any] = {key: _parse_scalar(value)} if value else {key: {}}
            child, index = _parse_mapping(lines, index, indent + 2)
            item.update(child)
            items.append(item)
        else:
            items.append(_parse_scalar(item_text))
    return items, index


def _parse_literal(lines: list[str], index: int, indent: int) -> tuple[str, int]:
    collected: list[str] = []
    while index < len(lines):
        line = lines[index]
        if line.strip() and _indent_of(line) < indent:
            break
        if not line.strip():
            collected.append("")
        else:
            collected.append(line[indent:])
        index += 1
    return "\n".join(collected).rstrip() + "\n", index


def _split_key_value(content: str) -> tuple[str, str]:
    if ":" not in content:
        raise ValueError(f"invalid YAML mapping line: {content}")
    key, value = content.split(":", 1)
    return key.strip(), value.strip()


def _parse_scalar(value: str) -> Any:
    value = _strip_inline_comment(value.strip())
    if value == "":
        return ""
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "Null", "none", "None", "~"}:
        return None
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]
    if _looks_like_quoted(value):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value


def _strip_inline_comment(value: str) -> str:
    if _looks_like_quoted(value):
        return value
    marker = " #"
    if marker in value:
        return value.split(marker, 1)[0].rstrip()
    return value


def _looks_like_quoted(value: str) -> bool:
    return len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}


def _skip_empty(lines: list[str], index: int) -> int:
    while index < len(lines) and (not lines[index].strip() or lines[index].lstrip().startswith("#")):
        index += 1
    return index


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _content(line: str) -> str:
    return line.strip()
