"""Build the Windows release with private source paths remapped, then audit it."""
from pathlib import Path
import argparse
import json
import os
import subprocess

from native_privacy import ROOT, require_clean_executable


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Use Cargo's existing dependency cache.")
    parser.add_argument("--target-dir", type=Path, default=ROOT / ".release-work/release-target")
    args = parser.parse_args()
    if os.name != "nt":
        raise SystemExit("This release script targets Windows x64.")
    env = os.environ.copy()
    target = args.target_dir.resolve()
    cargo_home = Path(env.get("CARGO_HOME", Path.home() / ".cargo")).resolve()
    sysroot = Path(subprocess.check_output(["rustc", "--print", "sysroot"], text=True).strip())
    mappings = [(Path.home(), "/build-user"), (sysroot, "/rust-toolchain"),
                (ROOT, "/paper-study-translator"), (target, "/build-target"),
                (cargo_home, "/cargo-home")]
    # Cargo uses whitespace-separated RUSTFLAGS or unit-separated encoded flags.
    # Append our remaps last so they win over inherited, overlapping remaps.
    encoded = env.get("CARGO_ENCODED_RUSTFLAGS")
    flags = encoded.split("\x1f") if encoded is not None else env.get("RUSTFLAGS", "").split()
    flags = [flag for flag in flags if flag]
    for path, replacement in mappings:
        for spelling in dict.fromkeys((str(path), path.as_posix())):
            flags.append(f"--remap-path-prefix={spelling}={replacement}")
    env["CARGO_ENCODED_RUSTFLAGS"] = "\x1f".join(flags)
    env.pop("RUSTFLAGS", None)
    env["CARGO_TARGET_DIR"] = str(target)
    subprocess.run(["npm.cmd", "run", "build"], cwd=ROOT / "apps/desktop", env=env, check=True)
    command = ["cargo", "build", "--release", "--features", "custom-protocol", "--locked"]
    if args.offline:
        command.append("--offline")
    subprocess.run(command, cwd=ROOT / "apps/desktop/src-tauri", env=env, check=True)
    executable = target / "release/qdt-gemini.exe"
    report = require_clean_executable(executable, [path for path, _ in mappings])
    print(json.dumps(report, indent=2), flush=True)
    print(f"Verified executable: {executable}", flush=True)


if __name__ == "__main__":
    main()
