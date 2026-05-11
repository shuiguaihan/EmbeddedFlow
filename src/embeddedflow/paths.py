from __future__ import annotations

from pathlib import Path


EF_DIRS = [
    "requirements",
    "recipes",
    "profiles",
    "artifacts",
    "runs",
    "knowledge",
]


def project_root(start: Path | None = None) -> Path:
    start = (start or Path.cwd()).resolve()
    for candidate in [start, *start.parents]:
        if (candidate / ".ef").is_dir() or (candidate / "ef.yaml").is_file():
            return candidate
    return start


def ef_dir(root: Path) -> Path:
    return root / ".ef"


def evidence_path(root: Path) -> Path:
    return ef_dir(root) / "evidence.jsonl"


def ensure_structure(root: Path, profile: str | None = None) -> None:
    base = ef_dir(root)
    for dirname in EF_DIRS:
        (base / dirname).mkdir(parents=True, exist_ok=True)
    if profile:
        profile_dir = base / "profiles" / profile
        profile_dir.mkdir(parents=True, exist_ok=True)
        profile_file = profile_dir / "profile.yaml"
        if not profile_file.exists():
            profile_file.write_text(f"id: {profile}\nname: {profile}\n", encoding="utf-8")
        local = profile_dir / "local.env.yaml"
        if not local.exists():
            local.write_text("# Local machine overrides; keep secrets out of git.\n", encoding="utf-8")
    config = root / "ef.yaml"
    if not config.exists():
        default_profile = profile or "default"
        config.write_text(
            "project:\n"
            f"  id: {root.name}\n"
            f"  name: {root.name}\n"
            "  repo_root: .\n"
            f"default_profile: {default_profile}\n"
            "recipe_defaults:\n"
            "  timeout: 300\n"
            "  shell: /bin/bash\n"
            "policy:\n"
            "  evidence_required: true\n",
            encoding="utf-8",
        )
    gitignore = root / ".gitignore"
    entries = [
        ".ef/evidence.jsonl",
        ".ef/artifacts/",
        ".ef/runs/",
        ".ef/profiles/*/local.env.yaml",
        ".ef/profiles/*/local.secrets.env",
    ]
    existing = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    with gitignore.open("a", encoding="utf-8") as handle:
        if existing and existing[-1] != "":
            handle.write("\n")
        for entry in entries:
            if entry not in existing:
                handle.write(entry + "\n")
