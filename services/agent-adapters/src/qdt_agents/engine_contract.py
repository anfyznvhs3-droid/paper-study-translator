from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class EngineRequest:
    engine_id: str
    document_profile_path: Path
    glossary_path: Path
    modal_policy_path: Path
    input_queue_path: Path
    output_filled_queue_path: Path
    output_mode: str
    token_estimate_path: Path
    source_language: str = "en"
    target_language: str = "ko"


@dataclass
class EngineResult:
    status: str
    message: str
    filled_queue_path: Path | None = None
    warnings: list[str] = field(default_factory=list)


class TranslationEngine(Protocol):
    def run(self, request: EngineRequest) -> EngineResult:
        """Run or prepare a translation engine handoff for a queue request."""
