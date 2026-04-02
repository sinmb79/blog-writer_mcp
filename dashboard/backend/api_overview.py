"""
dashboard/backend/api_overview.py
Overview 탭 API — KPI, 파이프라인 상태, 활동 로그
"""
import json
import re
from datetime import datetime, date
from pathlib import Path
from typing import List

from fastapi import APIRouter

BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
CONFIG_DIR = BASE_DIR / "config"

router = APIRouter()

CORNER_LABELS = {
    "easy_world": "쉬운세상",
    "hidden_gem": "숨은보물",
    "vibe": "바이브",
    "fact_check": "팩트체크",
    "deep_dive": "딥다이브",
    "novel": "연재소설",
}


def _count_published_files() -> dict:
    """published 폴더에서 오늘/이번주/총 발행 수 카운트"""
    published_dir = DATA_DIR / "published"
    if not published_dir.exists():
        return {"today": 0, "this_week": 0, "total": 0, "corners": {}}

    today = date.today()
    week_start = today.toordinal() - today.weekday()

    today_count = 0
    week_count = 0
    total_count = 0
    corner_counts: dict = {}

    for f in published_dir.glob("*.json"):
        total_count += 1
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            published_at_str = data.get("published_at", "")
            corner = data.get("corner", "기타")

            corner_counts[corner] = corner_counts.get(corner, 0) + 1

            if published_at_str:
                try:
                    pub_date = datetime.fromisoformat(
                        published_at_str[:19]
                    ).date()
                    if pub_date == today:
                        today_count += 1
                    if pub_date.toordinal() >= week_start:
                        week_count += 1
                except Exception:
                    pass
        except Exception:
            pass

    return {
        "today": today_count,
        "this_week": week_count,
        "total": total_count,
        "corners": corner_counts,
    }


def _get_revenue() -> dict:
    """analytics 폴더에서 수익 데이터 읽기"""
    analytics_dir = DATA_DIR / "analytics"
    if not analytics_dir.exists():
        return {"amount": 0.0, "currency": "USD", "status": "대기중"}

    latest = None
    for f in sorted(analytics_dir.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if "revenue" in data:
                latest = data["revenue"]
                break
        except Exception:
            pass

    if latest is None:
        return {"amount": 0.0, "currency": "USD", "status": "대기중"}
    return latest


def _parse_pipeline_status() -> List[dict]:
    """scheduler.log에서 파이프라인 단계별 상태 파싱"""
    steps = [
        {"id": "collector", "name": "수집", "status": "waiting", "done_at": ""},
        {"id": "writer", "name": "글쓰기", "status": "waiting", "done_at": ""},
        {"id": "converter", "name": "변환", "status": "waiting", "done_at": ""},
        {"id": "publisher", "name": "발행", "status": "waiting", "done_at": ""},
        {"id": "uploader", "name": "유튜브 업로드", "status": "waiting", "done_at": ""},
        {"id": "analytics", "name": "분석", "status": "waiting", "done_at": ""},
    ]

    log_file = LOGS_DIR / "scheduler.log"
    if not log_file.exists():
        return steps

    try:
        lines = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        today_str = date.today().strftime("%Y-%m-%d")

        for line in lines:
            if today_str not in line:
                continue
            low = line.lower()

            for step in steps:
                sid = step["id"]
                if sid in low:
                    # 타임스탬프 파싱
                    m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
                    ts = m.group(1)[11:16] if m else ""

                    if "완료" in line or "done" in low or "success" in low or "finish" in low:
                        step["status"] = "done"
                        step["done_at"] = ts
                    elif "시작" in line or "start" in low or "running" in low:
                        step["status"] = "running"
                        step["done_at"] = ts
                    elif "오류" in line or "error" in low or "fail" in low:
                        step["status"] = "error"
                        step["done_at"] = ts
    except Exception:
        pass

    return steps


def _get_activity_logs() -> List[dict]:
    """logs/*.log에서 최근 20개 활동 로그 파싱"""
    logs = []
    log_files = sorted(LOGS_DIR.glob("*.log"), key=lambda f: f.stat().st_mtime, reverse=True)

    for log_file in log_files[:5]:  # 최근 5개 파일만
        try:
            lines = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            for line in reversed(lines):
                if not line.strip():
                    continue
                m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),?\d*\s+\[(\w+)\]\s+(.*)", line)
                if m:
                    logs.append({
                        "time": m.group(1)[11:16],
                        "date": m.group(1)[:10],
                        "level": m.group(2),
                        "module": log_file.stem,
                        "message": m.group(3)[:120],
                    })
                    if len(logs) >= 20:
                        break
        except Exception:
            pass
        if len(logs) >= 20:
            break

    return logs[:20]


def _get_corner_ratio(corner_counts: dict) -> List[dict]:
    """코너별 발행 비율 계산"""
    total = sum(corner_counts.values()) or 1
    result = []
    for key, label in CORNER_LABELS.items():
        count = corner_counts.get(key, corner_counts.get(label, 0))
        result.append({
            "name": label,
            "count": count,
            "ratio": round(count / total * 100),
        })
    # 정의되지 않은 코너 추가
    known = set(CORNER_LABELS.keys()) | set(CORNER_LABELS.values())
    for k, v in corner_counts.items():
        if k not in known:
            result.append({
                "name": k,
                "count": v,
                "ratio": round(v / total * 100),
            })
    result.sort(key=lambda x: x["count"], reverse=True)
    return result


@router.get("/overview")
async def get_overview():
    counts = _count_published_files()
    revenue = _get_revenue()
    return {
        "kpi": {
            "today": counts["today"],
            "this_week": counts["this_week"],
            "total": counts["total"],
            "revenue": revenue,
        },
        "corner_ratio": _get_corner_ratio(counts["corners"]),
    }


@router.get("/pipeline")
async def get_pipeline():
    return {"steps": _parse_pipeline_status()}


@router.get("/activity")
async def get_activity():
    return {"logs": _get_activity_logs()}
