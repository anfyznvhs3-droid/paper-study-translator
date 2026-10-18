from __future__ import annotations

import argparse
from pathlib import Path

from .events import EventEmitter
from .job_runner import JobRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qdt-worker")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_job = subparsers.add_parser("run-job")
    run_job.add_argument("--job", required=True)
    run_job.add_argument("--project-dir", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "run-job":
        runner = JobRunner(EventEmitter())
        runner.run(Path(args.job), Path(args.project_dir))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

