"""
틱톡 배포봇 (distributors/tiktok_bot.py)
역할: 쇼츠 MP4 → TikTok Content Posting API 업로드 (LAYER 3)
Phase 2.

사전 조건:
- TikTok Developer 계정 + 앱 등록 (Content Posting API 승인)
- .env: TIKTOK_ACCESS_TOKEN, TIKTOK_OPEN_ID
"""
import json
import logging
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / '.env')

BASE_DIR = Path(__file__).parent.parent.parent
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)
DATA_DIR = BASE_DIR / 'data'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'distributor.log', encoding='utf-8'),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

TIKTOK_ACCESS_TOKEN = os.getenv('TIKTOK_ACCESS_TOKEN', '')
TIKTOK_OPEN_ID = os.getenv('TIKTOK_OPEN_ID', '')
TIKTOK_API_BASE = 'https://open.tiktokapis.com/v2'

CORNER_HASHTAGS = {
    '쉬운세상': ['쉬운세상', 'AI활용', '디지털라이프', 'The4thPath'],
    '숨은보물': ['숨은보물', 'AI도구', '생산성', 'The4thPath'],
    '바이브리포트': ['바이브리포트', '트렌드', 'AI시대', 'The4thPath'],
    '팩트체크': ['팩트체크', 'AI뉴스', 'The4thPath'],
    '한컷': ['한컷만평', 'AI시사', 'The4thPath'],
}


def _check_credentials() -> bool:
    if not TIKTOK_ACCESS_TOKEN:
        logger.warning("TIKTOK_ACCESS_TOKEN 없음")
        return False
    return True


def _get_headers() -> dict:
    return {
        'Authorization': f'Bearer {TIKTOK_ACCESS_TOKEN}',
        'Content-Type': 'application/json; charset=UTF-8',
    }


def build_caption(article: dict) -> str:
    """틱톡 캡션 생성 (제목 + 핵심 1줄 + 해시태그)"""
    title = article.get('title', '')
    key_points = article.get('key_points', [])
    corner = article.get('corner', '')

    caption_parts = [title]
    if key_points:
        caption_parts.append(key_points[0])

    hashtags = CORNER_HASHTAGS.get(corner, ['The4thPath'])
    tag_str = ' '.join(f'#{t}' for t in hashtags)
    caption_parts.append(tag_str)

    return '\n'.join(caption_parts)


def init_upload(video_size: int, video_duration: float) -> tuple[str, str]:
    """
    TikTok 업로드 초기화 (Direct Post).
    Returns: (upload_url, publish_id)
    """
    url = f'{TIKTOK_API_BASE}/post/publish/video/init/'
    payload = {
        'post_info': {
            'title': '',   # 영상에서 추출되므로 빈칸 가능
            'privacy_level': 'PUBLIC_TO_EVERYONE',
            'disable_duet': False,
            'disable_comment': False,
            'disable_stitch': False,
        },
        'source_info': {
            'source': 'FILE_UPLOAD',
            'video_size': video_size,
            'chunk_size': min(video_size, 64 * 1024 * 1024),  # 64MB
            'total_chunk_count': 1,
        },
    }
    try:
        resp = requests.post(url, json=payload, headers=_get_headers(), timeout=30)
        resp.raise_for_status()
        data = resp.json().get('data', {})
        upload_url = data.get('upload_url', '')
        publish_id = data.get('publish_id', '')
        logger.info(f"TikTok 업로드 초기화: publish_id={publish_id}")
        return upload_url, publish_id
    except Exception as e:
        logger.error(f"TikTok 업로드 초기화 실패: {e}")
        return '', ''


def upload_chunk(upload_url: str, video_path: str, video_size: int) -> bool:
    """동영상 업로드"""
    try:
        with open(video_path, 'rb') as f:
            video_data = f.read()
        headers = {
            'Content-Range': f'bytes 0-{video_size-1}/{video_size}',
            'Content-Length': str(video_size),
            'Content-Type': 'video/mp4',
        }
        resp = requests.put(upload_url, data=video_data, headers=headers, timeout=300)
        if resp.status_code in (200, 201, 206):
            logger.info("TikTok 동영상 업로드 완료")
            return True
        logger.error(f"TikTok 업로드 HTTP {resp.status_code}: {resp.text[:200]}")
        return False
    except Exception as e:
        logger.error(f"TikTok 업로드 실패: {e}")
        return False


def check_publish_status(publish_id: str, max_wait: int = 120) -> bool:
    """발행 상태 확인 (최대 max_wait초 대기)"""
    url = f'{TIKTOK_API_BASE}/post/publish/status/fetch/'
    payload = {'publish_id': publish_id}
    for _ in range(max_wait // 5):
        try:
            resp = requests.post(url, json=payload, headers=_get_headers(), timeout=10)
            resp.raise_for_status()
            status = resp.json().get('data', {}).get('status', '')
            if status == 'PUBLISH_COMPLETE':
                logger.info("TikTok 발행 완료")
                return True
            if status in ('FAILED', 'CANCELED'):
                logger.error(f"TikTok 발행 실패: {status}")
                return False
        except Exception as e:
            logger.warning(f"상태 확인 오류: {e}")
        time.sleep(5)
    logger.warning("TikTok 발행 상태 확인 시간 초과")
    return False


def publish_shorts(article: dict, video_path: str) -> bool:
    """
    쇼츠 MP4 → TikTok 업로드.
    video_path: shorts_converter.convert()가 생성한 MP4
    """
    if not _check_credentials():
        logger.info("TikTok 미설정 — 발행 건너뜀")
        return False

    if not Path(video_path).exists():
        logger.error(f"영상 파일 없음: {video_path}")
        return False

    title = article.get('title', '')
    logger.info(f"TikTok 발행 시작: {title}")

    video_size = Path(video_path).stat().st_size

    # 업로드 초기화
    upload_url, publish_id = init_upload(video_size, 30.0)
    if not upload_url or not publish_id:
        return False

    # 동영상 업로드
    if not upload_chunk(upload_url, video_path, video_size):
        return False

    # 발행 상태 확인
    if not check_publish_status(publish_id):
        return False

    _log_published(article, publish_id, 'tiktok')
    return True


def _log_published(article: dict, post_id: str, platform: str):
    pub_dir = DATA_DIR / 'published'
    pub_dir.mkdir(exist_ok=True)
    from datetime import datetime
    record = {
        'platform': platform,
        'post_id': post_id,
        'title': article.get('title', ''),
        'corner': article.get('corner', ''),
        'published_at': datetime.now().isoformat(),
    }
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{platform}_{post_id}.json"
    with open(pub_dir / filename, 'w', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    sample = {
        'title': '테스트 글',
        'corner': '쉬운세상',
        'key_points': ['포인트 1'],
    }
    print(build_caption(sample))
