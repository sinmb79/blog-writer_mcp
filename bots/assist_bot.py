"""
bots/assist_bot.py
수동(어시스트) 모드 파이프라인

흐름:
  1. 사용자 → URL 제공
  2. 시스템 → URL 파싱 → 콘텐츠 추출
  3. 시스템 → OpenClaw로 이미지/영상/나레이션 프롬프트 생성
  4. 사용자 → 웹 AI로 에셋 생성 후 제공 (대시보드 업로드 or inbox 폴더 드롭)
  5. 시스템 → 에셋 검증 → 배포 파이프라인 연결
"""
import json
import logging
import os
import re
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / '.env')

BASE_DIR = Path(__file__).parent.parent
ASSIST_DIR  = BASE_DIR / 'data' / 'assist'
SESSIONS_DIR = ASSIST_DIR / 'sessions'
INBOX_DIR    = ASSIST_DIR / 'inbox'
LOG_DIR      = BASE_DIR / 'logs'

for _d in [SESSIONS_DIR, INBOX_DIR, LOG_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    _h = logging.FileHandler(LOG_DIR / 'assist_bot.log', encoding='utf-8')
    _h.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(_h)
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.INFO)

_CLI = 'openclaw.cmd' if os.name == 'nt' else 'openclaw'


# ─── 상태 상수 ───────────────────────────────────────────

class S:
    PENDING    = 'pending'     # URL 접수됨
    FETCHING   = 'fetching'    # URL 수집 중
    GENERATING = 'generating'  # 프롬프트 생성 중
    AWAITING   = 'awaiting'    # 에셋 대기 중
    ASSEMBLING = 'assembling'  # 조립 중
    READY      = 'ready'       # 배포 준비 완료
    ERROR      = 'error'       # 오류

STATUS_LABEL = {
    S.PENDING:    '접수됨',
    S.FETCHING:   'URL 수집 중',
    S.GENERATING: '프롬프트 생성 중',
    S.AWAITING:   '에셋 대기 중',
    S.ASSEMBLING: '조립 중',
    S.READY:      '배포 준비 완료',
    S.ERROR:      '오류',
}

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.webm'}


# ─── 세션 I/O ────────────────────────────────────────────

def session_dir(sid: str) -> Path:
    return SESSIONS_DIR / sid

def meta_path(sid: str) -> Path:
    return session_dir(sid) / 'meta.json'

def load_session(sid: str) -> Optional[dict]:
    p = meta_path(sid)
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else None

def save_session(data: dict) -> None:
    sid = data['session_id']
    session_dir(sid).mkdir(parents=True, exist_ok=True)
    meta_path(sid).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8'
    )

def list_sessions() -> list:
    result = []
    if not SESSIONS_DIR.exists():
        return result
    for d in sorted(SESSIONS_DIR.iterdir(), reverse=True):
        if d.is_dir():
            p = meta_path(d.name)
            if p.exists():
                try:
                    result.append(json.loads(p.read_text(encoding='utf-8')))
                except Exception:
                    pass
    return result


# ─── URL 파싱 ────────────────────────────────────────────

def fetch_article(url: str) -> dict:
    """URL에서 제목과 본문을 추출한다."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    html = resp.text

    # 제목
    m = re.search(r'<title[^>]*>([^<]+)</title>', html, re.I)
    title = re.sub(r'\s*[–\-|]\s*.+$', '', m.group(1)).strip() if m else '제목 없음'

    # 본문 — 블로거/워드프레스/일반 HTML 순서로 시도
    body = ''
    for pat in [
        r'<div[^>]+class="[^"]*post-body[^"]*"[^>]*>(.*?)</div\s*>',
        r'<article[^>]*>(.*?)</article>',
        r'<div[^>]+class="[^"]*entry-content[^"]*"[^>]*>(.*?)</div\s*>',
        r'<main[^>]*>(.*?)</main>',
    ]:
        mm = re.search(pat, html, re.DOTALL | re.I)
        if mm:
            body = mm.group(1)
            break
    if not body:
        body = html

    body = re.sub(r'<[^>]+>', ' ', body)
    body = re.sub(r'\s+', ' ', body).strip()[:4000]
    return {'title': title, 'body': body, 'url': url}


# ─── 프롬프트 생성 ───────────────────────────────────────

def _prompt_request(title: str, body: str) -> str:
    return f"""아래 블로그 글을 읽고, 유튜브 쇼츠(60초 이내) 영상을 만들기 위한 프롬프트를 생성해줘.

제목: {title}
본문:
{body[:2000]}

반드시 아래 JSON 형식만 출력하고 다른 설명은 하지 마.

{{
  "image_prompts": [
    {{
      "purpose": "썸네일",
      "ko": "썸네일용 이미지 설명 (한국어)",
      "en": "Thumbnail image prompt for Midjourney/DALL-E, photorealistic, cinematic"
    }},
    {{
      "purpose": "배경1",
      "ko": "영상 배경 이미지 설명 (한국어)",
      "en": "Background image prompt, widescreen 16:9"
    }},
    {{
      "purpose": "배경2",
      "ko": "영상 배경 이미지 설명2 (한국어)",
      "en": "Second background image prompt, widescreen 16:9"
    }}
  ],
  "video_prompt": {{
    "ko": "AI 영상 생성용 설명 (한국어, 핵심 장면 요약)",
    "en": "Scene Overview: 15-second cinematic shot [location]. [mood1], [mood2], [genre] atmosphere.\\n\\nCharacters: [visual description].\\n\\nAction Flow:\\n- [step1]\\n[step2]\\n[step3]\\nSmooth fade out to black.\\n\\nDialogue:\\n캐릭터: \\"[핵심 메시지를 담은 한국어 대사]\"\\n\\nAudio: [ambient sound], [effect sound], [voice tone]."
  }},
  "narration_script": "쇼츠 나레이션 스크립트 (30-60초 분량, 한국어, 자막 스타일)"
}}"""


def generate_prompts(title: str, body: str) -> dict:
    """OpenClaw blog-writer 에이전트로 프롬프트를 생성한다."""
    try:
        result = subprocess.run(
            [_CLI, 'agent', '--agent', 'blog-writer',
             '--message', _prompt_request(title, body), '--json'],
            capture_output=True, timeout=180,
        )
        stderr_str = result.stderr.decode('utf-8', errors='replace').strip()
        if result.returncode != 0:
            logger.error(f"OpenClaw returncode={result.returncode} stderr={stderr_str[:200]}")
        elif not result.stdout:
            logger.error(f"OpenClaw stdout 비어있음 stderr={stderr_str[:200]}")
        else:
            stdout = result.stdout.decode('utf-8', errors='replace').strip()
            data = json.loads(stdout)
            raw = data.get('result', {}).get('payloads', [{}])[0].get('text', '')
            m = re.search(r'\{[\s\S]*\}', raw)
            if m:
                return json.loads(m.group())
            logger.warning(f"프롬프트 JSON 없음, raw={raw[:100]}")
    except Exception as e:
        logger.error(f"프롬프트 생성 오류: {e}")

    # 폴백
    return {
        "image_prompts": [
            {"purpose": "썸네일", "ko": f"{title} 썸네일", "en": f"Thumbnail: {title}, cinematic, photorealistic"},
            {"purpose": "배경1",  "ko": "추상적 기술 배경",  "en": "Abstract technology background, dark blue, 16:9"},
            {"purpose": "배경2",  "ko": "미니멀 배경",       "en": "Clean minimal background, soft light, 16:9"},
        ],
        "video_prompt": {
            "ko": f"{title}의 핵심 메시지를 담은 15초 시네마틱 영상",
            "en": (
                f"Scene Overview: 15-second cinematic shot in a modern dark space. "
                f"Informative, cinematic, and engaging atmosphere.\n\n"
                f"Characters: A glowing central figure representing the topic of {title}.\n\n"
                f"Action Flow:\n"
                f"- The figure stands in a dark space. Soft particles gather around it.\n"
                f"Camera slowly zooms in. Key visual elements emerge from the background.\n"
                f"The light intensifies. The camera pulls back to reveal the full scene.\n"
                f"Smooth fade out to black.\n\n"
                f"Dialogue:\n캐릭터: \"{title}에 대해 알아야 할 것들.\"\n\n"
                f"Audio: Cinematic ambient drone, subtle data-pulse sound, calm narrator voice."
            ),
        },
        "narration_script": f"{title}에 대해 알아봅시다. {body[:200]}",
    }


# ─── 파이프라인 ──────────────────────────────────────────

def create_session(url: str) -> dict:
    sid = datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:6]
    session = {
        'session_id': sid,
        'url': url,
        'status': S.PENDING,
        'status_label': STATUS_LABEL[S.PENDING],
        'created_at': datetime.now().isoformat(),
        'title': '',
        'body_preview': '',
        'prompts': {},
        'assets': [],
        'error': '',
    }
    save_session(session)
    logger.info(f"[어시스트] 새 세션: {sid} — {url}")
    return session


def run_pipeline(sid: str) -> None:
    """백그라운드 파이프라인 실행."""
    session = load_session(sid)
    if not session:
        return

    def _update(status: str, **kwargs):
        session['status'] = status
        session['status_label'] = STATUS_LABEL[status]
        session.update(kwargs)
        save_session(session)

    # 1. URL 수집
    _update(S.FETCHING)
    try:
        article = fetch_article(session['url'])
        _update(S.FETCHING,
                title=article['title'],
                body_preview=article['body'][:300],
                _full_body=article['body'])
        logger.info(f"[어시스트] URL 파싱 완료: {article['title']}")
    except Exception as e:
        _update(S.ERROR, error=f"URL 수집 실패: {e}")
        logger.error(f"[어시스트] {sid} URL 오류: {e}")
        return

    # 2. 프롬프트 생성
    _update(S.GENERATING)
    try:
        prompts = generate_prompts(session['title'], session.get('_full_body', ''))
        _update(S.AWAITING, prompts=prompts)
        logger.info(f"[어시스트] 프롬프트 준비 완료: {sid}")
    except Exception as e:
        _update(S.ERROR, error=f"프롬프트 생성 실패: {e}")
        return

    # 3. 에셋 대기 (사용자 업로드 or inbox 드롭 대기)
    logger.info(f"[어시스트] 에셋 대기 중: {sid}")


# ─── 에셋 관리 ───────────────────────────────────────────

def link_asset(sid: str, file_path: str) -> bool:
    """파일을 세션 assets/ 에 복사하고 메타에 등록한다."""
    session = load_session(sid)
    if not session:
        return False
    p = Path(file_path)
    ext = p.suffix.lower()
    asset_type = 'video' if ext in VIDEO_EXTENSIONS else 'image'

    assets_dir = session_dir(sid) / 'assets'
    assets_dir.mkdir(exist_ok=True)
    dest = assets_dir / p.name
    shutil.copy2(file_path, dest)

    session.setdefault('assets', []).append({
        'type': asset_type,
        'path': str(dest),
        'filename': p.name,
        'added_at': datetime.now().isoformat(),
    })
    save_session(session)
    logger.info(f"[어시스트] 에셋 등록: {sid} ← {p.name} ({asset_type})")
    return True


def scan_inbox(sid: str) -> list:
    """inbox 폴더에서 세션 ID 앞 8자리 접두사 파일을 자동 연결한다."""
    found = []
    prefix = sid[:8]
    for f in INBOX_DIR.iterdir():
        if f.is_file() and (f.name.startswith(prefix) or prefix in f.name):
            if link_asset(sid, str(f)):
                f.unlink(missing_ok=True)
                found.append(f.name)
    return found
