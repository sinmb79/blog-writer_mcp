"""
dashboard/backend/api_logs.py
Logs 탭 API — 시스템 로그 파싱, 필터/검색
"""
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query

BASE_DIR = Path(__file__).parent.parent.parent
LOGS_DIR = BASE_DIR / "logs"

router = APIRouter()

LOG_MODULES = {
    "": "전체",
    "scheduler": "스케줄러",
    "collector": "수집",
    "writer": "글쓰기",
    "converter": "변환",
    "publisher": "발행",
    "analytics": "분석",
    "novel": "소설",
    "engine_loader": "엔진",
    "error": "에러만",
}

LOG_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})[,\.]?\d*\s+"
    r"\[?(\w+)\]?\s+(.*)"
)


def _parse_log_line(line: str, module: str) -> dict | None:
    m = LOG_PATTERN.match(line.strip())
    if not m:
        return None
    return {
        "time": m.group(1),
        "level": m.group(2).upper(),
        "module": module,
        "message": m.group(3)[:300],
    }


def _read_logs(
    filter_module: str = "",
    search: str = "",
    limit: int = 200,
) -> list:
    logs = []

    if not LOGS_DIR.exists():
        return logs

    # 로그 파일 목록 (최근 수정 순)
    log_files = sorted(LOGS_DIR.glob("*.log"), key=lambda f: f.stat().st_mtime, reverse=True)

    error_only = filter_module == "error"

    for log_file in log_files:
        module_name = log_file.stem  # e.g. "scheduler", "collector"

        # 모듈 필터
        if filter_module and not error_only and module_name != filter_module:
            continue

        try:
            lines = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            for line in reversed(lines):
                if not line.strip():
                    continue
                entry = _parse_log_line(line, module_name)
                if entry is None:
                    continue

                # 에러만 필터
                if error_only and entry["level"] not in ("ERROR", "CRITICAL", "WARNING"):
                    continue

                # 검색 필터
                if search and search.lower() not in entry["message"].lower():
                    continue

                logs.append(entry)
                if len(logs) >= limit:
                    break
        except Exception:
            pass

        if len(logs) >= limit:
            break

    return logs[:limit]


@router.get("/logs")
async def get_logs(
    filter: str = Query(default="", description="모듈 필터 (scheduler/collector/writer/converter/publisher/error)"),
    search: str = Query(default="", description="메시지 검색"),
    limit: int = Query(default=200, ge=1, le=1000),
):
    logs = _read_logs(filter_module=filter, search=search, limit=limit)
    return {
        "logs": logs,
        "total": len(logs),
        "modules": LOG_MODULES,
    }
