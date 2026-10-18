from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class WorkerEvent:
    event: str
    job_id: str
    project_id: str
    stage: str
    progress: int
    message: str
    file_id: str | None = None
    artifact_paths: dict[str, str] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


class EventEmitter:
    def __init__(self, stream: Any | None = None) -> None:
        self._stream = stream or sys.stdout

    def emit(self, event: WorkerEvent) -> None:
        self._stream.write(event.to_json() + "\n")
        self._stream.flush()

