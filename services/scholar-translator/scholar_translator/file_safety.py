"""Input ownership and non-destructive output allocation."""
from pathlib import Path
import os
import re

GENERATED_DIRECTORIES = {"qdt_output", ".qdt-agent", ".qdt-home"}

def reserve_output_directory(base, label):
    """mkdir is the reservation: concurrent runs cannot claim the same output."""
    root = Path(base)
    root.mkdir(parents=True, exist_ok=True)
    label = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", label).strip(" .")[:160] or "document"
    if label.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        label = "_" + label
    for index in range(1, 10_000):
        target = root / (label if index == 1 else f"{label}-{index}")
        try:
            target.mkdir(exist_ok=False)
        except FileExistsError:
            continue
        (target / ".qdt-output").write_text("QDT generated output v1\n", encoding="utf-8")
        return target
    raise FileExistsError("No available output directory; prior results were preserved.")

def find_input_pdfs(directory, output_path=None):
    source = Path(directory).resolve()
    if not source.is_dir():
        raise ValueError(f"The provided path '{directory}' is not a directory.")
    excluded = Path(output_path).resolve() if output_path else None
    if excluded == source:
        excluded = None  # Only generated subdirectories are excluded in this case.
    paths = []
    for root, directories, files in os.walk(source, followlinks=False):
        current = Path(root)
        if (current / ".qdt-output").exists() or current.name.casefold() in GENERATED_DIRECTORIES or current == excluded:
            directories[:] = []
            continue
        directories[:] = sorted(
            name for name in directories
            if name.casefold() not in GENERATED_DIRECTORIES
            and not (current / name).is_symlink()
            and not getattr(os.path, "isjunction", lambda _: False)(current / name)
            and (current / name).resolve() != excluded
        )
        for name in sorted(files):
            path = current / name
            if path.suffix.lower() == ".pdf" and not path.is_symlink():
                paths.append(str(path))
    return paths
