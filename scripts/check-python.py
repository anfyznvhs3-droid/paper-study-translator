"""Run service tests against this checkout with isolated config/cache directories."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / ".qdt-home" / "tmp"
SCRATCH.mkdir(parents=True, exist_ok=True)
RUN = Path(tempfile.mkdtemp(prefix="check-all-", dir=SCRATCH))
SUITES = [
    ("translator-core", "tests", ["src", "../agent-adapters/src", "../scholar-translator"]),
    ("agent-adapters", "tests", ["src", "../translator-core/src", "../scholar-translator"]),
    ("worker", "tests", ["src", "../translator-core/src", "../agent-adapters/src", "../scholar-translator"]),
    ("mixed-renderer", ".", [".", "../scholar-translator", "../translator-core/src"]),
    ("scholar-translator", "tests", ["."]),
]
failed = False
for service, target, paths in SUITES:
    env = os.environ.copy()
    env.update(
        PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
        XDG_CACHE_HOME=str(ROOT / ".qdt-home" / ".cache"),
        PYTHONPATH=os.pathsep.join(paths),
    )
    for key in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        env.pop(key, None)
    config_path = RUN / (service + "-config.json")
    config_path.write_text("{}", encoding="utf-8")
    code = (
        "from pathlib import Path; import pytest; "
        "from scholar_translator.config import ConfigManager; "
        "config=object.__new__(ConfigManager); config._initialized=True; "
        f"config._config_path=Path({str(config_path)!r}); config._config_data={{}}; "
        "ConfigManager._instance=config; "
        f"raise SystemExit(pytest.main([{target!r},'-q','-p','no:cacheprovider','--basetemp',{str(RUN / service)!r}]))"
    )
    print(f"\n==> {service} tests", flush=True)
    try:
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-B", "-c", code],
            cwd=ROOT / "services" / service, env=env,
            capture_output=True, text=True, encoding="utf-8", timeout=180,
        )
        output = result.stdout + result.stderr
        print(output, flush=True)
        failed |= result.returncode != 0
    except subprocess.TimeoutExpired:
        output = "Verification timeout after 180 seconds.\n"
        print(output, flush=True)
        failed = True
    (RUN / (service + ".txt")).write_text(output, encoding="utf-8")
print(f"Verification logs: {RUN}")
raise SystemExit(1 if failed else 0)
