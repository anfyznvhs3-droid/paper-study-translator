from __future__ import annotations

from pathlib import Path


def ensure_project_dirs(project_dir: Path) -> dict[str, Path]:
    paths = {
        "input": project_dir / "input",
        "work": project_dir / "work",
        "review": project_dir / "review",
        "output": project_dir / "output",
        "reports": project_dir / "reports",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths

