from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from qdt_worker.events import EventEmitter
from qdt_worker.job_runner import JobRunner


class WorkerEventTests(unittest.TestCase):
    def test_worker_emits_jsonl_events_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job_path = root / "job.json"
            project_dir = root / "project"
            job_path.write_text(
                json.dumps(
                    {
                        "job_id": "job-1",
                        "project_id": "project-1",
                        "source_language": "en",
                        "target_language": "ko",
                        "review_mode": "review_on",
                        "translation_mode": "agent",
                        "engine_id": "codex_agent",
                        "output_mode": "mono",
                        "files": [],
                    }
                ),
                encoding="utf-8",
            )
            stream = io.StringIO()
            result = JobRunner(EventEmitter(stream)).run(job_path, project_dir)
            events = [json.loads(line) for line in stream.getvalue().splitlines()]

            self.assertEqual(result.status, "completed_with_warnings")
            self.assertTrue(result.report_path.exists())
            self.assertEqual(events[0]["event"], "job.created")
            self.assertIn("translation.tokens.estimated", [event["event"] for event in events])
            self.assertEqual(events[-1]["event"], "job.completed")


if __name__ == "__main__":
    unittest.main()

