from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

from .yaml_compat import safe_load


def _digest_prefix(parts: Iterable[bytes]) -> str:
    hasher = hashlib.sha256()
    for part in parts:
        hasher.update(part)
    return hasher.hexdigest()[:12]


def compute_source_hash(watch_patterns: list[str], project_root: Path) -> str:
    root = project_root.resolve()
    matched: set[Path] = set()
    for pattern in watch_patterns:
        for path in root.glob(pattern):
            if path.is_file():
                matched.add(path.resolve())
    chunks: list[bytes] = []
    for path in sorted(matched, key=lambda p: p.relative_to(root).as_posix()):
        rel = path.relative_to(root).as_posix()
        chunks.append(rel.encode("utf-8"))
        chunks.append(b"\0")
        chunks.append(path.read_bytes())
        chunks.append(b"\0")
    return _digest_prefix(chunks)


def compute_recipe_hash(recipe_path: Path) -> str:
    content = safe_load(recipe_path.read_text()) or {}
    canonical = json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
