"""
dashboard/backend/api_novels.py
Novel 탭 API — 소설 목록, 새 소설 생성, 에피소드 생성
"""
import json
import sys
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

BASE_DIR = Path(__file__).parent.parent.parent
NOVELS_CONFIG_DIR = BASE_DIR / "config" / "novels"
NOVELS_DATA_DIR = BASE_DIR / "data" / "novels"

router = APIRouter()


class NewNovelRequest(BaseModel):
    novel_id: str
    title: str
    title_ko: str
    genre: str
    setting: str
    characters: str
    base_story: str
    publish_schedule: str = "매주 월/목 09:00"
    episode_count_target: int = 50


@router.get("/novels")
async def get_novels():
    """config/novels/*.json 읽어 반환"""
    NOVELS_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    novels = []

    for path in sorted(NOVELS_CONFIG_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))

            # 에피소드 수 계산
            ep_dir = NOVELS_DATA_DIR / data.get("novel_id", path.stem) / "episodes"
            ep_files = list(ep_dir.glob("ep*.json")) if ep_dir.exists() else []
            ep_files = [
                f for f in ep_files
                if "_summary" not in f.name and "_blog" not in f.name
            ]

            data["episode_files"] = len(ep_files)

            # 에피소드 목록 로드
            episodes = []
            for ef in sorted(ep_files, key=lambda x: x.name)[-10:]:  # 최근 10개
                try:
                    ep_data = json.loads(ef.read_text(encoding="utf-8"))
                    episodes.append({
                        "episode_num": ep_data.get("episode_num", 0),
                        "title": ep_data.get("title", ""),
                        "generated_at": ep_data.get("generated_at", "")[:10],
                        "word_count": ep_data.get("word_count", 0),
                    })
                except Exception:
                    pass
            data["episodes"] = episodes

            # 진행률
            target = data.get("episode_count_target", 0)
            current = data.get("current_episode", len(ep_files))
            data["progress"] = round(current / target * 100) if target else 0

            novels.append(data)
        except Exception:
            pass

    return {"novels": novels}


@router.post("/novels")
async def create_novel(req: NewNovelRequest):
    """새 소설 config 생성"""
    NOVELS_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    config_path = NOVELS_CONFIG_DIR / f"{req.novel_id}.json"
    if config_path.exists():
        raise HTTPException(status_code=409, detail="이미 존재하는 소설 ID입니다.")

    novel_config = {
        "novel_id": req.novel_id,
        "title": req.title,
        "title_ko": req.title_ko,
        "genre": req.genre,
        "setting": req.setting,
        "characters": req.characters,
        "base_story": req.base_story,
        "publish_schedule": req.publish_schedule,
        "episode_count_target": req.episode_count_target,
        "current_episode": 0,
        "status": "active",
        "created_at": datetime.now().isoformat(),
        "episode_log": [],
    }

    config_path.write_text(
        json.dumps(novel_config, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # 데이터 디렉터리 생성
    novel_data_dir = NOVELS_DATA_DIR / req.novel_id
    for sub in ["episodes", "shorts", "images"]:
        (novel_data_dir / sub).mkdir(parents=True, exist_ok=True)

    return {"success": True, "novel_id": req.novel_id, "message": f"소설 '{req.title_ko}' 생성 완료"}


@router.post("/novels/{novel_id}/generate")
async def generate_episode(novel_id: str):
    """다음 에피소드 생성 — NovelManager.run_episode_pipeline() 호출"""
    config_path = NOVELS_CONFIG_DIR / f"{novel_id}.json"
    if not config_path.exists():
        raise HTTPException(status_code=404, detail="소설을 찾을 수 없습니다.")

    try:
        sys.path.insert(0, str(BASE_DIR / "bots"))
        sys.path.insert(0, str(BASE_DIR / "bots" / "novel"))
        from bots.novel.novel_manager import NovelManager
        manager = NovelManager()
        ok = manager.run_episode_pipeline(novel_id, telegram_notify=False)
        if ok:
            status = manager.get_novel_status(novel_id)
            return {
                "success": True,
                "episode_num": status.get("current_episode", 0),
                "message": f"에피소드 생성 완료",
            }
        else:
            raise HTTPException(status_code=500, detail="에피소드 생성 실패 — 로그 확인")
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"모듈 로드 실패: {e}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/novels/{novel_id}/episodes")
async def get_episodes(novel_id: str):
    """소설 에피소드 전체 목록"""
    ep_dir = NOVELS_DATA_DIR / novel_id / "episodes"
    if not ep_dir.exists():
        return {"episodes": []}

    episodes = []
    for ef in sorted(ep_dir.glob("ep*.json"), key=lambda x: x.name):
        if "_summary" in ef.name or "_blog" in ef.name:
            continue
        try:
            ep_data = json.loads(ef.read_text(encoding="utf-8"))
            episodes.append({
                "episode_num": ep_data.get("episode_num", 0),
                "title": ep_data.get("title", ""),
                "generated_at": ep_data.get("generated_at", "")[:10],
                "word_count": ep_data.get("word_count", 0),
                "published": ep_data.get("published", False),
            })
        except Exception:
            pass

    return {"episodes": episodes}
