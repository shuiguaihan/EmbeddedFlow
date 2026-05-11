from __future__ import annotations

import json
from typing import Any

from .yaml_compat import safe_dump


def dump_data(data: Any, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if fmt == "yaml":
        return safe_dump(data, allow_unicode=True, sort_keys=False)
    raise ValueError(f"unsupported format: {fmt}")
