import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


class DomainAlreadyExists(FileExistsError):
    """Raised when a domain slug already exists."""


class DomainNotFound(FileNotFoundError):
    """Raised when a domain or its glossary.csv is not found."""


VALID_STATUSES = {"candidate", "confirmed", "rejected"}


@dataclass(frozen=True)
class GlossaryEntry:
    source: str
    target: str
    notes: str = ""


@dataclass(frozen=True)
class TermDecision:
    source: str
    target: str
    status: str
    confidence: str
    origin: str
    ts: str


@dataclass(frozen=True)
class DomainMemory:
    display_name: str
    slug: str
    path: Path


class DomainMemoryStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def create_domain(self, display_name: str, slug: str | None = None) -> DomainMemory:
        domain_slug = slug or _slugify(display_name)
        domain_path = self.root / domain_slug
        if domain_path.exists():
            raise DomainAlreadyExists(f"Domain slug already exists: {domain_slug}")

        domain_path.mkdir(parents=True)
        (domain_path / "domain.json").write_text(
            json.dumps(
                {"display_name": display_name, "slug": domain_slug},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        _write_glossary(domain_path / "glossary.csv")
        for name in ["term-decisions.jsonl", "phrase-memory.jsonl", "rejected-terms.jsonl"]:
            (domain_path / name).write_text("", encoding="utf-8")
        (domain_path / "review-rules.md").write_text("# Review Rules\n", encoding="utf-8")

        return DomainMemory(display_name=display_name, slug=domain_slug, path=domain_path)

    def load_glossary(self, slug: str) -> list[GlossaryEntry]:
        return self._read_all(self._require_glossary(slug))

    def add_term(self, slug: str, source: str, target: str, notes: str = "") -> None:
        glossary_path = self._require_glossary(slug)
        entries = self._read_all(glossary_path)
        source_lower = source.strip().lower()

        updated = False
        for i, entry in enumerate(entries):
            if entry.source.lower() == source_lower:
                entries[i] = GlossaryEntry(source=entry.source, target=target, notes=notes)
                updated = True
                break

        if not updated:
            entries.append(GlossaryEntry(source=source.strip(), target=target, notes=notes))

        self._write_all(glossary_path, entries)

    def delete_term(self, slug: str, source: str) -> bool:
        glossary_path = self._require_glossary(slug)
        entries = self._read_all(glossary_path)
        source_lower = source.strip().lower()

        new_entries = [e for e in entries if e.source.lower() != source_lower]
        if len(new_entries) == len(entries):
            return False

        self._write_all(glossary_path, new_entries)
        return True

    def record_decision(
        self,
        slug: str,
        source: str,
        target: str,
        status: str,
        confidence: str = "high",
        origin: str = "user",
    ) -> None:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status!r}. Must be one of {VALID_STATUSES}")
        domain_path = self._require_domain(slug)
        ts = datetime.now(timezone.utc).isoformat()
        decision = TermDecision(
            source=source,
            target=target,
            status=status,
            confidence=confidence,
            origin=origin,
            ts=ts,
        )
        decisions_path = domain_path / "term-decisions.jsonl"
        with decisions_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(
                {
                    "source": decision.source,
                    "target": decision.target,
                    "status": decision.status,
                    "confidence": decision.confidence,
                    "origin": decision.origin,
                    "ts": decision.ts,
                },
                ensure_ascii=False,
            ) + "\n")

    def list_decisions(self, slug: str) -> list[TermDecision]:
        domain_path = self._require_domain(slug)
        decisions_path = domain_path / "term-decisions.jsonl"
        if not decisions_path.exists():
            return []
        decisions: list[TermDecision] = []
        with decisions_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                decisions.append(TermDecision(
                    source=data["source"],
                    target=data["target"],
                    status=data["status"],
                    confidence=data.get("confidence", ""),
                    origin=data.get("origin", ""),
                    ts=data.get("ts", ""),
                ))
        return decisions

    def list_candidates(self, slug: str) -> list[TermDecision]:
        all_decisions = self.list_decisions(slug)
        latest_by_source: dict[str, TermDecision] = {}
        for d in all_decisions:
            latest_by_source[d.source] = d
        return [d for d in latest_by_source.values() if d.status == "candidate"]

    def promote(self, slug: str, source: str) -> bool:
        all_decisions = self.list_decisions(slug)
        latest: TermDecision | None = None
        for d in all_decisions:
            if d.source.lower() == source.lower():
                latest = d
        if latest is None or latest.status != "candidate":
            return False
        self.add_term(slug, latest.source, latest.target)
        self.record_decision(slug, latest.source, latest.target, status="confirmed")
        return True

    def reject(self, slug: str, source: str, reason: str = "") -> None:
        self.record_decision(slug, source, "", status="rejected")
        domain_path = self._require_domain(slug)
        rejected_path = domain_path / "rejected-terms.jsonl"
        ts = datetime.now(timezone.utc).isoformat()
        with rejected_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(
                {"source": source, "reason": reason, "ts": ts},
                ensure_ascii=False,
            ) + "\n")

    def rejected_terms(self, slug: str) -> set[str]:
        domain_path = self._require_domain(slug)
        rejected_path = domain_path / "rejected-terms.jsonl"
        if not rejected_path.exists():
            return set()
        result: set[str] = set()
        with rejected_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                result.add(data.get("source", ""))
        return result

    def _require_domain(self, slug: str) -> Path:
        domain_path = self.root / slug
        if not domain_path.exists():
            raise DomainNotFound(f"Domain not found: {slug}")
        return domain_path

    def _require_glossary(self, slug: str) -> Path:
        domain_path = self.root / slug
        if not domain_path.exists():
            raise DomainNotFound(f"Domain not found: {slug}")
        glossary_path = domain_path / "glossary.csv"
        if not glossary_path.exists():
            raise DomainNotFound(f"Glossary not found: {slug}")
        return glossary_path

    def _read_all(self, glossary_path: Path) -> list[GlossaryEntry]:
        entries: list[GlossaryEntry] = []
        with glossary_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                source = row.get("source", "").strip()
                if not source:
                    continue
                entries.append(GlossaryEntry(
                    source=source,
                    target=row.get("target", ""),
                    notes=row.get("notes", ""),
                ))
        return entries

    def _write_all(self, glossary_path: Path, entries: list[GlossaryEntry]) -> None:
        with glossary_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["source", "target", "notes"])
            for entry in entries:
                writer.writerow([entry.source, entry.target, entry.notes])


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "domain"


def _write_glossary(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source", "target", "notes"])

