"""
dashboard/backend/api_settings.py
Settings 탭 API — engine.json 읽기/쓰기
"""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

BASE_DIR = Path(__file__).parent.parent.parent
CONFIG_PATH = BASE_DIR / "config" / "engine.json"

router = APIRouter()


class SettingsUpdate(BaseModel):
    data: dict


@router.get("/settings")
async def get_settings():
    """config/engine.json 반환"""
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"설정 파일 읽기 실패: {e}")


@router.put("/settings")
async def update_settings(req: SettingsUpdate):
    """config/engine.json 저장"""
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps(req.data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return {"success": True, "message": "설정 저장 완료"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"설정 저장 실패: {e}")
