"""
인스타그램 배포봇 (distributors/instagram_bot.py)
역할: 카드 이미지 → Instagram Graph API 업로드 (LAYER 3)
- 피드 포스트: 카드 이미지 업로드
- 릴스: 쇼츠 영상 업로드 (Phase 2)
- 캡션: KEY_POINTS + 해시태그 + 블로그 링크(프로필)

사전 조건:
- Facebook Page + Instagram Business 계정 연결
- Instagram Graph API 앱 등록
- .env: INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_ACCOUNT_ID
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

INSTAGRAM_ACCESS_TOKEN = os.getenv('INSTAGRAM_ACCESS_TOKEN', '')
INSTAGRAM_ACCOUNT_ID = os.getenv('INSTAGRAM_ACCOUNT_ID', '')
GRAPH_API_BASE = 'https://graph.facebook.com/v19.0'

BLOG_URL = 'https://the4thpath.com'
BRAND_TAG = '#The4thPath #테크인사이더 #22BLabs'


def _check_credentials() -> bool:
    if not INSTAGRAM_ACCESS_TOKEN or not INSTAGRAM_ACCOUNT_ID:
        logger.warning("Instagram 자격증명 없음 (.env: INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_ACCOUNT_ID)")
        return False
    return True


def build_caption(article: dict) -> str:
    """인스타그램 캡션 생성"""
    title = article.get('title', '')
    corner = article.get('corner', '')
    key_points = article.get('key_points', [])
    tags = article.get('tags', [])

    lines = [f"✨ {title}", ""]
    if key_points:
        for point in key_points[:3]:
            lines.append(f"• {point}")
        lines.append("")

    lines.append(f"전체 내용: 프로필 링크 🔗")
    lines.append("")

    hashtags = [f'#{corner.replace(" ", "")}'] if corner else []
    hashtags += [f'#{t}' for t in tags[:5] if t]
    hashtags.append(BRAND_TAG)
    lines.append(' '.join(hashtags))

    return '\n'.join(lines)


def upload_image_container(image_url: str, caption: str) -> str:
    """
    인스타 이미지 컨테이너 생성.
    image_url: 공개 접근 가능한 이미지 URL (Instagram이 직접 다운로드)
    Returns: container_id
    """
    if not _check_credentials():
        return ''

    url = f"{GRAPH_API_BASE}/{INSTAGRAM_ACCOUNT_ID}/media"
    params = {
        'image_url': image_url,
        'caption': caption,
        'access_token': INSTAGRAM_ACCESS_TOKEN,
    }
    try:
        resp = requests.post(url, data=params, timeout=30)
        resp.raise_for_status()
        container_id = resp.json().get('id', '')
        logger.info(f"이미지 컨테이너 생성: {container_id}")
        return container_id
    except Exception as e:
        logger.error(f"Instagram 컨테이너 생성 실패: {e}")
        return ''


def publish_container(container_id: str) -> str:
    """컨테이너 → 실제 발행. Returns: post_id"""
    if not _check_credentials() or not container_id:
        return ''

    # 컨테이너 준비 대기 (최대 60초)
    status_url = f"{GRAPH_API_BASE}/{container_id}"
    for _ in range(12):
        try:
            status_resp = requests.get(
                status_url,
                params={'fields': 'status_code', 'access_token': INSTAGRAM_ACCESS_TOKEN},
                timeout=10
            )
            status = status_resp.json().get('status_code', '')
            if status == 'FINISHED':
                break
            if status in ('ERROR', 'EXPIRED'):
                logger.error(f"컨테이너 오류: {status}")
                return ''
        except Exception:
            pass
        time.sleep(5)

    # 발행
    publish_url = f"{GRAPH_API_BASE}/{INSTAGRAM_ACCOUNT_ID}/media_publish"
    params = {
        'creation_id': container_id,
        'access_token': INSTAGRAM_ACCESS_TOKEN,
    }
    try:
        resp = requests.post(publish_url, data=params, timeout=30)
        resp.raise_for_status()
        post_id = resp.json().get('id', '')
        logger.info(f"Instagram 발행 완료: {post_id}")
        return post_id
    except Exception as e:
        logger.error(f"Instagram 발행 실패: {e}")
        return ''


def upload_video_container(video_url: str, caption: str) -> str:
    """
    Instagram Reels 업로드 컨테이너 생성.
    video_url: 공개 접근 가능한 MP4 URL
    Returns: container_id
    """
    if not _check_credentials():
        return ''

    url = f"{GRAPH_API_BASE}/{INSTAGRAM_ACCOUNT_ID}/media"
    params = {
        'media_type': 'REELS',
        'video_url': video_url,
        'caption': caption,
        'share_to_feed': 'true',
        'access_token': INSTAGRAM_ACCESS_TOKEN,
    }
    try:
        resp = requests.post(url, data=params, timeout=30)
        resp.raise_for_status()
        container_id = resp.json().get('id', '')
        logger.info(f"Reels 컨테이너 생성: {container_id}")
        return container_id
    except Exception as e:
        logger.error(f"Instagram Reels 컨테이너 생성 실패: {e}")
        return ''


def wait_for_video_ready(container_id: str, max_wait: int = 300) -> bool:
    """
    비디오 컨테이너 처리 완료 대기 (최대 max_wait초).
    Reels는 인코딩 시간이 이미지보다 길다.
    """
    status_url = f"{GRAPH_API_BASE}/{container_id}"
    for _ in range(max_wait // 10):
        try:
            resp = requests.get(
                status_url,
                params={'fields': 'status_code', 'access_token': INSTAGRAM_ACCESS_TOKEN},
                timeout=10,
            )
            status = resp.json().get('status_code', '')
            if status == 'FINISHED':
                return True
            if status in ('ERROR', 'EXPIRED'):
                logger.error(f"Reels 컨테이너 오류: {status}")
                return False
            logger.debug(f"Reels 인코딩 중: {status}")
        except Exception as e:
            logger.warning(f"Reels 상태 확인 오류: {e}")
        time.sleep(10)
    logger.warning("Reels 컨테이너 준비 시간 초과")
    return False


def publish_reels(article: dict, video_path_or_url: str) -> bool:
    """
    쇼츠 MP4를 Instagram Reels로 게시.
    video_path_or_url: 로컬 MP4 파일 경로 또는 공개 MP4 URL
      - 로컬 경로인 경우 image_host.get_public_video_url()로 공개 URL 변환
      - http/https URL인 경우 그대로 사용
    """
    if not _check_credentials():
        logger.info("Instagram 미설정 — Reels 발행 건너뜀")
        return False

    logger.info(f"Instagram Reels 발행 시작: {article.get('title', '')}")

    # 로컬 경로 → 공개 URL 변환
    video_url = video_path_or_url
    if not video_path_or_url.startswith('http'):
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from image_host import get_public_video_url
        video_url = get_public_video_url(video_path_or_url)
        if not video_url:
            logger.error(
                "Reels 공개 URL 변환 실패 — .env에 VIDEO_HOST_BASE_URL 또는 "
                "LOCAL_IMAGE_SERVER=true (Tailscale) 설정 필요"
            )
            return False

    caption = build_caption(article)
    container_id = upload_video_container(video_url, caption)
    if not container_id:
        return False

    if not wait_for_video_ready(container_id):
        return False

    post_id = publish_container(container_id)
    if not post_id:
        return False

    _log_published(article, post_id, 'instagram_reels')
    return True


def publish_card(article: dict, image_path_or_url: str) -> bool:
    """
    카드 이미지를 인스타그램 피드에 게시.
    image_path_or_url: 로컬 파일 경로 또는 공개 URL
      - 로컬 경로인 경우 image_host.py로 공개 URL 변환
      - http/https URL인 경우 그대로 사용
    """
    if not _check_credentials():
        logger.info("Instagram 미설정 — 발행 건너뜀")
        return False

    logger.info(f"Instagram 발행 시작: {article.get('title', '')}")

    # 로컬 경로 → 공개 URL 변환
    image_url = image_path_or_url
    if not image_path_or_url.startswith('http'):
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from image_host import get_public_url
        image_url = get_public_url(image_path_or_url)
        if not image_url:
            logger.error("공개 URL 변환 실패 — .env에 IMGBB_API_KEY 설정 필요")
            return False

    caption = build_caption(article)
    container_id = upload_image_container(image_url, caption)
    if not container_id:
        return False

    post_id = publish_container(container_id)
    if not post_id:
        return False

    _log_published(article, post_id, 'instagram_card')
    return True


def _log_published(article: dict, post_id: str, platform: str):
    """플랫폼별 발행 이력 저장"""
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
    # 테스트 (실제 API 없이 출력 확인)
    sample = {
        'title': '테스트 글',
        'corner': '쉬운세상',
        'key_points': ['포인트 1', '포인트 2'],
        'tags': ['AI', '테스트'],
    }
    print(build_caption(sample))
