import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SourceBlock:
    document_id: str
    page_number: int
    block_id: str
    text: str
    classifier: str | None = None


@dataclass(frozen=True)
class TranslationQueueItem:
    source: SourceBlock
    korean: str | None = None


@dataclass(frozen=True)
class TranslationQueue:
    items: list[TranslationQueueItem]

    def write_json(self, path: str | Path) -> None:
        _write_queue(path, self.items)

    @classmethod
    def read_json(cls, path: str | Path) -> "TranslationQueue":
        return cls(items=_read_items(path))


@dataclass(frozen=True)
class FilledTranslationQueue:
    items: list[TranslationQueueItem]

    def write_json(self, path: str | Path) -> None:
        _write_queue(path, self.items)

    @classmethod
    def read_json(cls, path: str | Path) -> "FilledTranslationQueue":
        return cls(items=_read_items(path))


def _write_queue(path: str | Path, items: list[TranslationQueueItem]) -> None:
    payload = {"items": [asdict(item) for item in items]}
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_items(path: str | Path) -> list[TranslationQueueItem]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return [_item_from_dict(item) for item in payload.get("items", [])]


def _item_from_dict(value: dict[str, Any]) -> TranslationQueueItem:
    source = SourceBlock(**value["source"])
    return TranslationQueueItem(source=source, korean=value.get("korean"))

