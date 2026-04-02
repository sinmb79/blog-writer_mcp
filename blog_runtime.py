"""
Single safe launcher for project runtime entrypoints.
"""
from __future__ import annotations

import runpy
import subprocess
import sys
from pathlib import Path

from runtime_guard import (
    PROJECT_ROOT,
    ensure_project_runtime,
    load_required_distributions,
    project_python_cmd,
)


CLI_REQUIREMENTS = ["requests"]
SERVER_REQUIREMENTS = ["fastapi", "uvicorn", "python-dotenv", "python-multipart"]
SCHEDULER_REQUIREMENTS = ["apscheduler", "python-dotenv", "python-telegram-bot", "anthropic"]


def _run_subprocess(args: list[str]) -> int:
    completed = subprocess.run(project_python_cmd(args), cwd=str(PROJECT_ROOT))
    return completed.returncode


def main() -> None:
    args = sys.argv[1:]

    if not args:
        sys.argv = [str(PROJECT_ROOT / "blog_engine_cli.py")]
        ensure_project_runtime("blog CLI", CLI_REQUIREMENTS)
        runpy.run_path(str(PROJECT_ROOT / "blog_engine_cli.py"), run_name="__main__")
        return

    command = args[0].lower()
    rest = args[1:]

    if command == "server":
        ensure_project_runtime("dashboard server", SERVER_REQUIREMENTS)
        raise SystemExit(
            _run_subprocess(
                ["-m", "uvicorn", "dashboard.backend.server:app", "--host", "0.0.0.0", "--port", "8080", *rest]
            )
        )

    if command == "scheduler":
        ensure_project_runtime("scheduler", SCHEDULER_REQUIREMENTS)
        raise SystemExit(_run_subprocess([str(PROJECT_ROOT / "bots" / "scheduler.py"), *rest]))

    if command == "python":
        ensure_project_runtime("project python", load_required_distributions())
        raise SystemExit(_run_subprocess(rest))

    sys.argv = [str(PROJECT_ROOT / "blog_engine_cli.py"), *args]
    ensure_project_runtime("blog CLI", CLI_REQUIREMENTS)
    runpy.run_path(str(PROJECT_ROOT / "blog_engine_cli.py"), run_name="__main__")


if __name__ == "__main__":
    main()
