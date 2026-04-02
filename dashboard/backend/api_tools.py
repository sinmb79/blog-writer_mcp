"""
dashboard/backend/api_tools.py
Settings > 생성도구 선택 탭 API
"""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

BASE_DIR = Path(__file__).parent.parent.parent
CONFIG_PATH = BASE_DIR / "config" / "engine.json"

router = APIRouter()

TOOL_CATEGORIES = {
    "writing": {
        "label": "글쓰기",
        "options": ["claude", "gemini", "openclaw"],
        "option_labels": {
            "claude": "Claude (Anthropic)",
            "gemini": "Google Gemini",
            "openclaw": "OpenClaw AI",
        },
    },
    "image_generation": {
        "label": "이미지 생성",
        "options": ["dalle", "external"],
        "option_labels": {
            "dalle": "DALL-E 3 (OpenAI)",
            "external": "수동 제공",
        },
    },
    "tts": {
        "label": "TTS (음성합성)",
        "options": ["google_cloud", "openai", "elevenlabs", "gtts"],
        "option_labels": {
            "google_cloud": "Google Cloud TTS",
            "openai": "OpenAI TTS (tts-1-hd)",
            "elevenlabs": "ElevenLabs",
            "gtts": "gTTS (무료)",
        },
    },
    "video_generation": {
        "label": "영상 생성",
        "options": ["ffmpeg_slides", "seedance", "runway", "sora", "veo"],
        "option_labels": {
            "ffmpeg_slides": "FFmpeg 슬라이드 (로컬)",
            "seedance": "Seedance 2.0",
            "runway": "Runway Gen-3",
            "sora": "OpenAI Sora",
            "veo": "Google Veo",
        },
    },
}


class ToolUpdate(BaseModel):
    tools: dict  # {"writing": "claude", "tts": "gtts", ...}


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


@router.get("/tools")
async def get_tools():
    """현재 선택된 도구 + 선택 가능 목록 반환"""
    config = _load_config()
    result = {}

    for category, meta in TOOL_CATEGORIES.items():
        current = config.get(category, {}).get("provider", meta["options"][0])
        result[category] = {
            "label": meta["label"],
            "current": current,
            "options": [
                {
                    "value": opt,
                    "label": meta["option_labels"].get(opt, opt),
                }
                for opt in meta["options"]
            ],
        }

    return {"tools": result}


@router.put("/tools")
async def update_tools(req: ToolUpdate):
    """engine.json 도구 섹션 업데이트"""
    config = _load_config()

    for category, provider in req.tools.items():
        if category in TOOL_CATEGORIES:
            if category not in config:
                config[category] = {}
            config[category]["provider"] = provider

    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps(config, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return {"success": True, "message": "도구 설정 저장 완료"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"저장 실패: {e}")
