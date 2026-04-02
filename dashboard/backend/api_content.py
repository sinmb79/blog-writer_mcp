"""
dashboard/backend/api_content.py
Content 탭 API — 칸반 보드, 승인/거부, 수동 트리거
"""
import json
import subprocess
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from runtime_guard import project_python_path, run_with_project_python

BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = BASE_DIR / "data"

router = APIRouter()


class WriteRequest(BaseModel):
    topic: str = ""


def _read_folder_cards(folder: Path, status: str) -> list:
    """폴더에서 JSON 파일을 읽어 칸반 카드 목록 반환"""
    cards = []
    if not folder.exists():
        return cards

    for f in sorted(folder.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            cards.append({
                "id": f.stem,
                "file": str(f),
                "title": data.get("title", f.stem),
                "corner": data.get("corner", ""),
                "source": data.get("source", ""),
                "quality_score": data.get("quality_score", data.get("score", 0)),
                "created_at": data.get("created_at", data.get("collected_at", "")),
                "status": status,
                "summary": data.get("summary", data.get("body", "")[:200] if data.get("body") else ""),
            })
        except Exception:
            pass
    return cards


@router.get("/content")
async def get_content():
    """칸반 4열 데이터 반환"""
    queue = _read_folder_cards(DATA_DIR / "topics", "queue")
    queue += _read_folder_cards(DATA_DIR / "collected", "queue")

    writing = _read_folder_cards(DATA_DIR / "drafts", "writing")

    review = _read_folder_cards(DATA_DIR / "pending_review", "review")

    published = _read_folder_cards(DATA_DIR / "published", "published")[:20]

    return {
        "queue": queue,
        "writing": writing,
        "review": review,
        "published": published,
        "columns": {
            "queue": {"label": "글감큐", "cards": queue},
            "writing": {"label": "작성중", "cards": writing},
            "review": {"label": "검수대기", "cards": review},
            "published": {"label": "발행완료", "cards": published},
        }
    }


@router.post("/content/{item_id}/approve")
async def approve_content(item_id: str):
    """검수 승인 — pending_review → published로 이동"""
    src = DATA_DIR / "pending_review" / f"{item_id}.json"
    if not src.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

    try:
        data = json.loads(src.read_text(encoding="utf-8"))
        data["approved_at"] = datetime.now().isoformat()
        data["status"] = "approved"

        dst = DATA_DIR / "published" / f"{item_id}.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        src.unlink(missing_ok=True)

        return {"success": True, "message": f"{item_id} 승인 완료"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/content/{item_id}/reject")
async def reject_content(item_id: str):
    """검수 거부 — pending_review → discarded로 이동"""
    src = DATA_DIR / "pending_review" / f"{item_id}.json"
    if not src.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")

    try:
        data = json.loads(src.read_text(encoding="utf-8"))
        data["rejected_at"] = datetime.now().isoformat()
        data["status"] = "rejected"

        dst = DATA_DIR / "discarded" / f"{item_id}.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        src.unlink(missing_ok=True)

        return {"success": True, "message": f"{item_id} 거부 완료"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/manual-write")
async def manual_write(req: WriteRequest):
    """collector_bot + writer_bot 수동 트리거"""
    bots_dir = BASE_DIR / "bots"
    python = project_python_path()

    if not python.exists():
        raise HTTPException(
            status_code=500,
            detail=(
                f"프로젝트 가상환경 Python이 없습니다: {python}. "
                "venv 생성 후 requirements.txt를 설치하세요."
            ),
        )

    results = []

    # collector_bot 실행
    collector = bots_dir / "collector_bot.py"
    if collector.exists():
        try:
            result = run_with_project_python(
                [str(collector)],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(BASE_DIR),
                encoding="utf-8",
            )
            results.append({
                "step": "collector",
                "success": result.returncode == 0,
                "python": str(python),
                "output": result.stdout[-500:] if result.stdout else "",
                "error": result.stderr[-300:] if result.stderr else "",
            })
        except subprocess.TimeoutExpired:
            results.append({"step": "collector", "success": False, "python": str(python), "error": "타임아웃"})
        except Exception as e:
            results.append({"step": "collector", "success": False, "python": str(python), "error": str(e)})
    else:
        results.append({"step": "collector", "success": False, "python": str(python), "error": "파일 없음"})

    # writer_bot 실행
    writer = bots_dir / "writer_bot.py"
    if writer.exists():
        try:
            result = run_with_project_python(
                [str(writer)],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(BASE_DIR),
                encoding="utf-8",
            )
            results.append({
                "step": "writer",
                "success": result.returncode == 0,
                "python": str(python),
                "output": result.stdout[-500:] if result.stdout else "",
                "error": result.stderr[-300:] if result.stderr else "",
            })
        except subprocess.TimeoutExpired:
            results.append({"step": "writer", "success": False, "python": str(python), "error": "타임아웃"})
        except Exception as e:
            results.append({"step": "writer", "success": False, "python": str(python), "error": str(e)})
    else:
        results.append({"step": "writer", "success": False, "python": str(python), "error": "파일 없음"})

    return {"python": str(python), "results": results}
