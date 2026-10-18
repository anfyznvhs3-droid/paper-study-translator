"""Reject developer paths and credential patterns in the application executable."""
from pathlib import Path
import argparse
import json
import os
import re

ROOT = Path(__file__).resolve().parents[1]
PATH_RULES = {
    "absolute Rust source path": re.compile(
        r"(?i)(?<![a-z0-9])[a-z]:[\\/][^\x00\r\n<>|\"?*]{1,500}?[\\/][^\\/\x00\r\n<>|\"?*]{1,150}\.rs\b"
    ),
    "developer home path": re.compile(
        r"(?i)(?<![a-z0-9])[a-z]:[\\/]+(?:Users[\\/]+(?!Public\b|Default\b)[^\\/\s\x00]+|OneDrive[\\/])"
    ),
    "build cache path": re.compile(
        r"(?i)(?<![a-z0-9])[a-z]:[\\/][^\x00\r\n<>|\"?*]{0,500}?(?:\.cargo|\.qdt-home|\.release-work|registry[\\/]src)[\\/]"
    ),
}
SECRET_RULES = {
    "Google API key": rb"AIza[0-9A-Za-z_-]{35}",
    "provider secret": rb"\bsk-(?:proj-|ant-)[A-Za-z0-9_-]{20,}",
    "GitHub token": rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})",
}


def scan_bytes(data: bytes, private_roots=()) -> list[dict]:
    findings = []
    # Either alignment can occur in a PE section. UTF-8 covers ASCII paths too.
    for encoding, text in (
        ("utf-8", data.decode("utf-8", errors="replace")),
        ("utf-16le-even", data.decode("utf-16le", errors="replace")),
        ("utf-16le-odd", data[1:].decode("utf-16le", errors="replace")),
    ):
        for name, pattern in PATH_RULES.items():
            count = sum(1 for _ in pattern.finditer(text))
            if count:
                findings.append({"rule": name, "encoding": encoding, "count": count})
        normalized = text.replace("\\", "/").lower()
        for index, root in enumerate(private_roots):
            root = str(root).replace("\\", "/").rstrip("/").lower()
            if root and (count := normalized.count(root + "/")):
                findings.append({"rule": "build-machine root", "root_index": index,
                                 "encoding": encoding, "count": count})
    for name, pattern in SECRET_RULES.items():
        if count := len(re.findall(pattern, data)):
            findings.append({"rule": name, "encoding": "bytes", "count": count})
    return findings


def audit_executable(executable: Path, private_roots=()) -> dict:
    roots = [ROOT, Path.home()]
    roots.extend(os.environ[k] for k in ("CARGO_HOME", "RUSTUP_HOME", "CARGO_TARGET_DIR") if os.environ.get(k))
    roots.extend(private_roots)
    data = executable.read_bytes()
    if data[:2] != b"MZ":
        raise ValueError("Expected a Windows executable.")
    findings = scan_bytes(data, roots)
    # Never print matched path or credential values, even on failure.
    return {"ok": not findings, "file": executable.name, "bytes": len(data), "findings": findings}


def require_clean_executable(executable: Path, private_roots=()) -> dict:
    report = audit_executable(executable, private_roots)
    if not report["ok"]:
        raise ValueError("Native privacy check failed: " + json.dumps(report))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    args = parser.parse_args()
    result = audit_executable(args.executable)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["ok"] else 1)
