"""
Shared runtime checks and project-Python helpers.
"""
from __future__ import annotations

import importlib.metadata
import os
import re
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"
VENV_DIR = PROJECT_ROOT / "venv"


def project_python_path() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _normalized(path: str | Path) -> str:
    return str(Path(path).resolve()).casefold()


def _parse_requirement_name(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    requirement = stripped.split(";", 1)[0].strip()
    requirement = re.split(r"[<>=!~]", requirement, 1)[0].strip()
    return requirement or None


def load_required_distributions() -> list[str]:
    if not REQUIREMENTS_FILE.exists():
        return []

    packages: list[str] = []
    for line in REQUIREMENTS_FILE.read_text(encoding="utf-8").splitlines():
        name = _parse_requirement_name(line)
        if name:
            packages.append(name)
    return packages


def missing_distributions(distributions: list[str]) -> list[str]:
    missing: list[str] = []
    for name in distributions:
        try:
            importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            missing.append(name)
    return missing


def ensure_project_runtime(
    entrypoint: str,
    required_distributions: list[str] | None = None,
) -> None:
    expected_python = project_python_path()
    current_python = Path(sys.executable)

    if not expected_python.exists():
        raise RuntimeError(
            f"{entrypoint} requires the project virtualenv at '{expected_python}'. "
            "Create it first and install requirements.txt."
        )

    if _normalized(current_python) != _normalized(expected_python):
        raise RuntimeError(
            f"{entrypoint} must run with the project virtualenv Python.\n"
            f"Current:  {current_python}\n"
            f"Expected: {expected_python}\n"
            f"Safe path: {expected_python} {PROJECT_ROOT / 'blog_runtime.py'} "
            f"{_default_launcher_arg(entrypoint)}"
        )

    missing = missing_distributions(required_distributions or [])
    if missing:
        raise RuntimeError(
            f"{entrypoint} is missing required packages in the project virtualenv: "
            f"{', '.join(missing)}\n"
            f"Install with: {expected_python} -m pip install -r {REQUIREMENTS_FILE}"
        )


def run_with_project_python(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    ensure_project_runtime("project subprocess")
    cmd = [str(project_python_path()), *args]
    return subprocess.run(cmd, **kwargs)


def project_python_cmd(args: list[str]) -> list[str]:
    return [str(project_python_path()), *args]


def _default_launcher_arg(entrypoint: str) -> str:
    lowered = entrypoint.lower()
    if "scheduler" in lowered:
        return "scheduler"
    if "server" in lowered or "dashboard" in lowered:
        return "server"
    return "status"
