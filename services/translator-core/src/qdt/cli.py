"""WIKI CLI - single interface for Tauri backend (task T2.6, part 1).

Each command prints a JSON result to stdout. `run_cli(argv)` returns that JSON string.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from qdt.classify.domain import propose_domain
from qdt.glossary_exchange import (
    export_glossary,
    import_glossary_entries,
    parse_glossary_exchange,
)
from qdt.memory import DomainMemoryStore


def run_cli(argv: list[str]) -> str:
    args = dict(_parse(argv))
    command = args.pop("_command", None)
    kb = args.pop("kb", None)
    domain = args.pop("domain", None)

    if not command or not kb:
        return json.dumps({"error": "Missing required args: command, --kb"}, ensure_ascii=False)

    # propose-domain doesn't require --domain
    if command == "propose-domain":
        text_file = args.get("text_file")
        if not text_file:
            return json.dumps({"error": "Missing --text-file"}, ensure_ascii=False)
        text = Path(text_file).read_text(encoding="utf-8")
        keyword_map = _build_keyword_map(kb)
        result_domain = propose_domain(text, keyword_map)
        return json.dumps({"domain": result_domain}, ensure_ascii=False)

    if not domain:
        return json.dumps({"error": "Missing required args: --domain"}, ensure_ascii=False)

    store = DomainMemoryStore(kb)

    if command == "list-glossary":
        entries = store.load_glossary(domain)
        result = [{"source": e.source, "target": e.target, "notes": e.notes} for e in entries]

    elif command == "add-term":
        store.add_term(domain, args["source"], args["target"], args.get("notes", ""))
        result = {"added": True}

    elif command == "delete-term":
        deleted = store.delete_term(domain, args["source"])
        result = {"deleted": deleted}

    elif command == "list-candidates":
        candidates = store.list_candidates(domain)
        result = [
            {
                "source": c.source,
                "target": c.target,
                "status": c.status,
                "confidence": c.confidence,
                "origin": c.origin,
                "ts": c.ts,
            }
            for c in candidates
        ]

    elif command == "promote":
        promoted = store.promote(domain, args["source"])
        result = {"promoted": promoted}

    elif command == "reject":
        store.reject(domain, args["source"], args.get("reason", ""))
        result = {"ok": True}

    elif command == "export-glossary":
        fmt = args.get("format", "omegat")
        out = args.get("out")
        if not out:
            return json.dumps({"error": "Missing --out"}, ensure_ascii=False)
        entries = store.load_glossary(domain)
        output = export_glossary(entries, fmt)
        output_path = Path(out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
        result = {"exported": len(entries), "path": str(output_path), "format": fmt}

    elif command == "import-glossary":
        fmt = args.get("format", "omegat")
        input_path = args.get("input")
        if not input_path:
            return json.dumps({"error": "Missing --input"}, ensure_ascii=False)
        mode = args.get("mode", "candidates")
        text = Path(input_path).read_text(encoding="utf-8")
        entries = parse_glossary_exchange(text, fmt)
        import_result = import_glossary_entries(store, domain, entries, mode)
        result = {**import_result, "format": fmt}

    elif command == "discover-terms":
        # Real LLM call — requires the agent CLI (codex/claude). Smoke tool.
        from qdt.discover import agent_llm, run_discovery

        source = Path(args["source_file"]).read_text(encoding="utf-8")
        translation = Path(args["translation_file"]).read_text(encoding="utf-8")
        llm = agent_llm(args.get("engine", "codex"), args.get("cli_path"))
        run_discovery(store, domain, source, translation, llm)
        candidates = store.list_candidates(domain)
        result = [
            {"source": c.source, "target": c.target, "confidence": c.confidence, "origin": c.origin}
            for c in candidates
        ]

    else:
        result = {"error": f"Unknown command: {command}"}

    return json.dumps(result, ensure_ascii=False)


def _build_keyword_map(kb_root: str) -> dict[str, list[str]]:
    root = Path(kb_root)
    keyword_map: dict[str, list[str]] = {}
    for domain_dir in root.iterdir():
        if not domain_dir.is_dir():
            continue
        if not (domain_dir / "domain.json").exists():
            continue
        slug = domain_dir.name
        store = DomainMemoryStore(kb_root)
        entries = store.load_glossary(slug)
        keyword_map[slug] = [e.source for e in entries]
    return keyword_map


def _parse(argv: list[str]) -> dict:
    result: dict = {}
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--kb" and i + 1 < len(argv):
            result["kb"] = argv[i + 1]
            i += 2
        elif arg == "--domain" and i + 1 < len(argv):
            result["domain"] = argv[i + 1]
            i += 2
        elif arg == "--source" and i + 1 < len(argv):
            result["source"] = argv[i + 1]
            i += 2
        elif arg == "--target" and i + 1 < len(argv):
            result["target"] = argv[i + 1]
            i += 2
        elif arg == "--notes" and i + 1 < len(argv):
            result["notes"] = argv[i + 1]
            i += 2
        elif arg == "--reason" and i + 1 < len(argv):
            result["reason"] = argv[i + 1]
            i += 2
        elif arg == "--text-file" and i + 1 < len(argv):
            result["text_file"] = argv[i + 1]
            i += 2
        elif arg == "--source-file" and i + 1 < len(argv):
            result["source_file"] = argv[i + 1]
            i += 2
        elif arg == "--translation-file" and i + 1 < len(argv):
            result["translation_file"] = argv[i + 1]
            i += 2
        elif arg == "--format" and i + 1 < len(argv):
            result["format"] = argv[i + 1]
            i += 2
        elif arg == "--out" and i + 1 < len(argv):
            result["out"] = argv[i + 1]
            i += 2
        elif arg == "--input" and i + 1 < len(argv):
            result["input"] = argv[i + 1]
            i += 2
        elif arg == "--mode" and i + 1 < len(argv):
            result["mode"] = argv[i + 1]
            i += 2
        elif arg == "--engine" and i + 1 < len(argv):
            result["engine"] = argv[i + 1]
            i += 2
        elif arg == "--cli-path" and i + 1 < len(argv):
            result["cli_path"] = argv[i + 1]
            i += 2
        elif not arg.startswith("--") and "_command" not in result:
            result["_command"] = arg
            i += 1
        else:
            i += 1
    return result


def main() -> None:
    print(run_cli(sys.argv[1:]))
    sys.exit(0)


if __name__ == "__main__":
    main()
