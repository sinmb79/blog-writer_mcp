"""
dashboard/backend/api_analytics.py
Analytics 탭 API — 방문자 통계, KPI, 코너별 성과
"""
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query

BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data"
ANALYTICS_DIR = DATA_DIR / "analytics"

router = APIRouter()


def _load_all_analytics() -> list:
    """analytics/*.json 전체 로드"""
    records = []
    if not ANALYTICS_DIR.exists():
        return records

    for f in sorted(ANALYTICS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, list):
                records.extend(data)
            elif isinstance(data, dict):
                records.append(data)
        except Exception:
            pass
    return records


def _aggregate_kpi(records: list) -> dict:
    total_visitors = sum(r.get("visitors", 0) for r in records)
    total_pageviews = sum(r.get("pageviews", 0) for r in records)
    avg_duration = 0
    avg_ctr = 0.0

    durations = [r.get("avg_duration_sec", 0) for r in records if r.get("avg_duration_sec")]
    if durations:
        avg_duration = int(sum(durations) / len(durations))

    ctrs = [r.get("ctr", 0.0) for r in records if r.get("ctr")]
    if ctrs:
        avg_ctr = round(sum(ctrs) / len(ctrs), 2)

    return {
        "visitors": total_visitors,
        "pageviews": total_pageviews,
        "avg_duration_sec": avg_duration,
        "ctr": avg_ctr,
    }


def _aggregate_corners(records: list) -> list:
    corner_map: dict = {}
    for r in records:
        corner = r.get("corner", "기타")
        if corner not in corner_map:
            corner_map[corner] = {"visitors": 0, "pageviews": 0, "posts": 0}
        corner_map[corner]["visitors"] += r.get("visitors", 0)
        corner_map[corner]["pageviews"] += r.get("pageviews", 0)
        corner_map[corner]["posts"] += r.get("post_count", 1)

    result = []
    for name, data in corner_map.items():
        result.append({"corner": name, **data})
    result.sort(key=lambda x: x["visitors"], reverse=True)
    return result


def _top_posts(records: list, limit: int = 5) -> list:
    posts = []
    for r in records:
        if "title" in r and "visitors" in r:
            posts.append({
                "title": r["title"],
                "visitors": r["visitors"],
                "views": r["visitors"],
                "corner": r.get("corner", ""),
                "published_at": r.get("date", ""),
            })
    posts.sort(key=lambda x: x["visitors"], reverse=True)
    return posts[:limit]


def _platform_performance(records: list) -> list:
    platform_map: dict = {}
    for r in records:
        platform = r.get("platform", "blogger")
        if platform not in platform_map:
            platform_map[platform] = {"visitors": 0, "posts": 0}
        platform_map[platform]["visitors"] += r.get("visitors", 0)
        platform_map[platform]["posts"] += 1

    return [{"platform": k, **v} for k, v in platform_map.items()]


@router.get("/analytics")
async def get_analytics():
    records = _load_all_analytics()
    kpi = _aggregate_kpi(records)
    top_posts = _top_posts(records)
    return {
        "visitors": kpi["visitors"],
        "pageviews": kpi["pageviews"],
        "avg_duration_sec": kpi["avg_duration_sec"],
        "ctr": kpi["ctr"],
        "kpi": kpi,
        "corners": _aggregate_corners(records),
        "top_posts": top_posts,
        "platforms": _platform_performance(records),
        "total_records": len(records),
    }


@router.get("/analytics/chart")
async def get_analytics_chart(days: int = Query(default=7, ge=1, le=365)):
    """days일간 방문자 시계열 데이터"""
    records = _load_all_analytics()

    today = date.today()
    date_range = [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]

    # 날짜별 집계
    daily: dict = {d: {"date": d, "visitors": 0, "pageviews": 0} for d in date_range}

    for r in records:
        d = r.get("date", "")[:10]
        if d in daily:
            daily[d]["visitors"] += r.get("visitors", 0)
            daily[d]["pageviews"] += r.get("pageviews", 0)

    return {"chart": list(daily.values()), "days": days}
