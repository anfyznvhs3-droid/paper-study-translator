"""Pytest environment isolation for the vendored translator package."""

import os
import tempfile
from pathlib import Path


repo_root = Path(__file__).resolve().parents[3]

if not os.environ.get("XDG_CACHE_HOME"):
    cache_home = repo_root / ".qdt-home" / ".cache"
    cache_home.mkdir(parents=True, exist_ok=True)
    os.environ["XDG_CACHE_HOME"] = str(cache_home)

tmp_home = repo_root / ".qdt-home" / "tmp"
tmp_home.mkdir(parents=True, exist_ok=True)
for name in ("TMPDIR", "TEMP", "TMP"):
    os.environ.setdefault(name, str(tmp_home))
tempfile.tempdir = str(tmp_home)
