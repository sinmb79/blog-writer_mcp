"""
dashboard/backend/api_cost.py
Settings > 비용관리 탭 API — 구독 정보, API 사용량
"""
import json
import re
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter

BASE_DIR = Path(__file__).parent.parent.parent
CONFIG_PATH = BASE_DIR / "config" / "engine.json"
LOGS_DIR = BASE_DIR / "logs"

router = APIRouter()

SUBSCRIPTION_PLANS = [
    {
        "id": "claude_pro",
        "name": "Claude Pro",
        "provider": "Anthropic",
        "monthly_cost_usd": 20.0,
        "env_key": "ANTHROPIC_API_KEY",
        "renewal_day": 1,  # 매월 1일 갱신
    },
    {
        "id": "openai_plus",
        "name": "OpenAI API",
        "provider": "OpenAI",
        "monthly_cost_usd": 0.0,  # 종량제
        "env_key": "OPENAI_API_KEY",
        "renewal_day": None,
    },
    {
        "id": "gemini_api",
        "name": "Google Gemini API",
        "provider": "Google",
        "monthly_cost_usd": 0.0,  # 무료 티어 + 종량제
        "env_key": "GEMINI_API_KEY",
        "renewal_day": None,
    },
    {
        "id": "elevenlabs",
        "name": "ElevenLabs Starter",
        "provider": "ElevenLabs",
        "monthly_cost_usd": 5.0,
        "env_key": "ELEVENLABS_API_KEY",
        "renewal_day": 1,
    },
]


def _days_until_renewal(renewal_day):
    if renewal_day is None:
        return None
    today = date.today()
    next_renewal = date(today.year, today.month, renewal_day)
    if next_renewal <= today:
        # 다음 달
        if today.month == 12:
            next_renewal = date(today.year + 1, 1, renewal_day)
        else:
            next_renewal = date(today.year, today.month + 1, renewal_day)
    return (next_renewal - today).days


def _parse_api_usage() -> list:
    """logs/*.log에서 API 사용량 파싱"""
    usage_map: dict = {}
    patterns = {
        "claude": re.compile(r"claude.*?(\d+)\s*토큰|tokens[:\s]+(\d+)", re.IGNORECASE),
        "openai": re.compile(r"openai.*?(\d+)\s*토큰|gpt.*?tokens[:\s]+(\d+)", re.IGNORECASE),
        "gemini": re.compile(r"gemini.*?(\d+)\s*토큰", re.IGNORECASE),
    }

    if not LOGS_DIR.exists():
        return []

    for log_file in LOGS_DIR.glob("*.log"):
        try:
            content = log_file.read_text(encoding="utf-8", errors="ignore")
            for provider, pattern in patterns.items():
                matches = pattern.findall(content)
                tokens = sum(int(m[0] or m[1] or 0) for m in matches if any(m))
                if tokens:
                    usage_map[provider] = usage_map.get(provider, 0) + tokens
        except Exception:
            pass

    result = []
    for provider, tokens in usage_map.items():
        result.append({
            "provider": provider,
            "tokens": tokens,
            "estimated_cost_usd": round(tokens / 1_000_000 * 3.0, 4),  # 근사치
        })
    return result


@router.get("/cost/subscriptions")
async def get_subscriptions():
    """구독 정보 + 만료일 계산"""
    import os
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / '.env')

    subscriptions = []
    for plan in SUBSCRIPTION_PLANS:
        key_set = bool(os.getenv(plan["env_key"], ""))
        days_left = _days_until_renewal(plan.get("renewal_day"))
        subscriptions.append({
            "id": plan["id"],
            "name": plan["name"],
            "provider": plan["provider"],
            "monthly_cost_usd": plan["monthly_cost_usd"],
            "active": key_set,
            "renewal_day": plan.get("renewal_day"),
            "days_until_renewal": days_left,
            "alert": days_left is not None and days_left <= 5,
        })

    total_monthly = sum(p["monthly_cost_usd"] for p in subscriptions if p["active"])
    return {
        "subscriptions": subscriptions,
        "total_monthly_usd": total_monthly,
    }


@router.get("/cost/usage")
async def get_usage():
    """logs에서 API 사용량 파싱"""
    return {"usage": _parse_api_usage()}
