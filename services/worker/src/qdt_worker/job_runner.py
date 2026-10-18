from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .events import EventEmitter, WorkerEvent
from .paths import ensure_project_dirs


@dataclass
class JobRunResult:
    status: str
    report_path: Path


class JobRunner:
    def __init__(self, emitter: EventEmitter) -> None:
        self.emitter = emitter

    def run(self, job_path: Path, project_dir: Path) -> JobRunResult:
        job = json.loads(job_path.read_text(encoding="utf-8"))
        job_id = job["job_id"]
        project_id = job["project_id"]
        dirs = ensure_project_dirs(project_dir)

        self._emit("job.created", job, "created", 0, "작업이 생성되었습니다.")
        self._emit(
            "translation.engine.selected",
            job,
            "engine",
            10,
            f"번역 엔진이 선택되었습니다: {job['engine_id']}",
            data={
                "translation_mode": job["translation_mode"],
                "engine_id": job["engine_id"],
                "output_mode": job["output_mode"],
            },
        )

        if job["translation_mode"] == "agent":
            self._emit(
                "translation.tokens.estimated",
                job,
                "estimate",
                20,
                "에이전트 모드 토큰/비용 예상이 준비되었습니다.",
                data={"pricing_basis": "cost unavailable"},
            )

        queue_path = dirs["work"] / "translation-queue.json"
        queue_path.write_text(
            json.dumps(
                {
                    "job_id": job_id,
                    "source_language": "en",
                    "target_language": "ko",
                    "items": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        self._emit(
            "translation.queue.created",
            job,
            "queue",
            35,
            "번역 큐가 생성되었습니다.",
            artifact_paths={"queue": str(queue_path)},
        )

        report_path = dirs["reports"] / "job-report.json"
        report = {
            "job_id": job_id,
            "status": "completed_with_warnings",
            "files": job.get("files", []),
            "errors": [],
            "warnings": ["MVP worker skeleton: translation engine execution is not connected yet."],
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        self._emit(
            "job.completed",
            job,
            "completed",
            100,
            "작업 골격 실행이 완료되었습니다.",
            artifact_paths={"report": str(report_path)},
        )
        return JobRunResult(status="completed_with_warnings", report_path=report_path)

    def _emit(
        self,
        event: str,
        job: dict[str, Any],
        stage: str,
        progress: int,
        message: str,
        artifact_paths: dict[str, str] | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        self.emitter.emit(
            WorkerEvent(
                event=event,
                job_id=job["job_id"],
                project_id=job["project_id"],
                stage=stage,
                progress=progress,
                message=message,
                artifact_paths=artifact_paths or {},
                data=data or {},
            )
        )

