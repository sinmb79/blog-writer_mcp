"""
dashboard/backend/api_assist.py
수동(어시스트) 모드 API
"""
import threading
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

BASE_DIR = Path(__file__).parent.parent.parent

router = APIRouter()

# assist_bot을 지연 임포트 (서버 기동 시 오류 방지)
def _bot():
    import sys
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    from bots import assist_bot
    return assist_bot


@router.post("/assist/session")
async def create_session(payload: dict):
    """URL을 받아 새 어시스트 세션을 생성하고 파이프라인을 시작한다."""
    url = payload.get('url', '').strip()
    if not url.startswith('http'):
        raise HTTPException(status_code=400, detail="유효한 URL을 입력하세요.")
    bot = _bot()
    session = bot.create_session(url)
    t = threading.Thread(
        target=bot.run_pipeline,
        args=(session['session_id'],),
        daemon=True,
    )
    t.start()
    return session


@router.get("/assist/sessions")
async def list_sessions():
    return _bot().list_sessions()


@router.get("/assist/session/{sid}")
async def get_session(sid: str):
    bot = _bot()
    # inbox 자동 스캔
    bot.scan_inbox(sid)
    session = bot.load_session(sid)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    return session


@router.post("/assist/session/{sid}/upload")
async def upload_asset(sid: str, file: UploadFile = File(...), asset_type: str = Form("image")):
    """에셋 파일 직접 업로드."""
    bot = _bot()
    session = bot.load_session(sid)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    assets_dir = bot.session_dir(sid) / 'assets'
    assets_dir.mkdir(parents=True, exist_ok=True)

    # 파일명 충돌 방지
    fname = file.filename or f"asset_{datetime.now().strftime('%H%M%S')}"
    dest = assets_dir / fname
    dest.write_bytes(await file.read())

    ext = dest.suffix.lower()
    detected_type = 'video' if ext in bot.VIDEO_EXTENSIONS else 'image'

    session.setdefault('assets', []).append({
        'type': detected_type,
        'path': str(dest),
        'filename': fname,
        'added_at': datetime.now().isoformat(),
    })
    bot.save_session(session)
    return {"ok": True, "filename": fname, "type": detected_type}


@router.delete("/assist/session/{sid}/asset/{filename}")
async def delete_asset(sid: str, filename: str):
    bot = _bot()
    session = bot.load_session(sid)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    session['assets'] = [a for a in session.get('assets', []) if a['filename'] != filename]
    bot.save_session(session)
    # 파일도 삭제
    p = bot.session_dir(sid) / 'assets' / filename
    p.unlink(missing_ok=True)
    return {"ok": True}


@router.get("/assist/inbox")
async def inbox_info():
    """inbox 폴더 경로 및 파일 목록 반환."""
    bot = _bot()
    inbox = bot.INBOX_DIR
    files = [f.name for f in inbox.iterdir() if f.is_file()] if inbox.exists() else []
    return {"path": str(inbox), "files": files, "count": len(files)}


@router.delete("/assist/session/{sid}")
async def delete_session(sid: str):
    import shutil
    bot = _bot()
    p = bot.session_dir(sid)
    if p.exists():
        shutil.rmtree(p)
    return {"ok": True}
