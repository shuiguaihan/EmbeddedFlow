from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import SSHConnection
from .yaml_compat import safe_load


class ConfigError(ValueError):
    pass


def load_yaml(path: Path, *, required: bool = True) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise ConfigError(f"missing YAML file: {path}")
        return {}
    data = safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"YAML root must be a mapping: {path}")
    return data


def load_project_config(root: Path, profile: str | None = None) -> dict[str, Any]:
    ef_config = load_yaml(root / "ef.yaml", required=False)
    profile_id = profile or ef_config.get("default_profile") or "default"
    profile_dir = root / ".ef" / "profiles" / str(profile_id)
    profile_data = load_yaml(profile_dir / "profile.yaml", required=False)
    local_env = load_yaml(profile_dir / "local.env.yaml", required=False)
    return {
        "ef": ef_config,
        "profile": profile_data,
        "local_env": local_env,
        "vars": ef_config.get("vars", {}) if isinstance(ef_config.get("vars", {}), dict) else {},
        "project": ef_config.get("project", {}) if isinstance(ef_config.get("project", {}), dict) else {},
    }


def resolve_connection(config: dict[str, Any], target_name: str) -> SSHConnection:
    local_env = config.get("local_env")
    if not isinstance(local_env, dict):
        raise ConfigError(f"no connection config for target: {target_name}")
    targets = local_env.get("targets")
    if not isinstance(targets, dict):
        raise ConfigError(f"no connection config for target: {target_name}")
    target = targets.get(target_name)
    if not isinstance(target, dict):
        raise ConfigError(f"no connection config for target: {target_name}")

    host = target.get("host")
    if not isinstance(host, str) or not host:
        raise ConfigError(f"connection target {target_name} missing host")

    port = target.get("port", 22)
    if isinstance(port, str) and port.isdigit():
        port = int(port)
    if not isinstance(port, int):
        raise ConfigError(f"connection target {target_name} has invalid port")

    user = target.get("user", "root")
    if not isinstance(user, str) or not user:
        raise ConfigError(f"connection target {target_name} has invalid user")

    auth_mode = target.get("auth_mode", "password")
    if auth_mode not in {"password", "key"}:
        raise ConfigError(f"connection target {target_name} has invalid auth_mode")

    password_env = target.get("password_env")
    key_path = target.get("key_path")
    return SSHConnection(
        host=host,
        port=port,
        user=user,
        auth_mode=auth_mode,
        password_env=password_env if isinstance(password_env, str) else None,
        key_path=key_path if isinstance(key_path, str) else None,
    )
