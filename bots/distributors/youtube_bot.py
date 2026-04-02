"""
유튜브 배포봇 (distributors/youtube_bot.py)
역할: 쇼츠 MP4 → YouTube Data API v3 업로드 (LAYER 3)
Phase 2.

사전 조건:
- Google Cloud에서 YouTube Data API v3 활성화 (기존 프로젝트에 추가)
- .env: YOUTUBE_CHANNEL_ID (기존 Google OAuth token.json 재사용)
"""
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / '.env')

BASE_DIR = Path(__file__).parent.parent.parent
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)
DATA_DIR = BASE_DIR / 'data'
TOKEN_PATH = BASE_DIR / 'token.json'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'distributor.log', encoding='utf-8'),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

YOUTUBE_CHANNEL_ID = os.getenv('YOUTUBE_CHANNEL_ID', '')

YOUTUBE_SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube',
]

CORNER_TAGS = {
    '쉬운세상': ['AI활용', '디지털라이프', '쉬운세상', 'The4thPath', 'AI가이드'],
    '숨은보물': ['숨은보물', 'AI도구', '생산성', 'The4thPath', 'AI툴'],
    '바이브리포트': ['트렌드', 'AI시대', '바이브리포트', 'The4thPath'],
    '팩트체크': ['팩트체크', 'AI뉴스', 'The4thPath'],
    '한컷': ['한컷만평', 'AI시사', 'The4thPath'],
}


def _get_credentials():
    """기존 Google OAuth token.json 재사용"""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        if not TOKEN_PATH.exists():
            raise RuntimeError("token.json 없음. scripts/get_token.py 먼저 실행")

        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), YOUTUBE_SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                TOKEN_PATH.write_text(creds.to_json())
        return creds
    except Exception as e:
        logger.error(f"YouTube 인증 실패: {e}")
        return None


def build_video_metadata(article: dict) -> dict:
    """유튜브 업로드용 메타데이터 구성"""
    title = article.get('title', '')
    meta = article.get('meta', '')
    corner = article.get('corner', '')
    key_points = article.get('key_points', [])
    slug = article.get('slug', '')

    # 쇼츠는 #Shorts 태그 필수
    description_parts = [meta, '']
    if key_points:
        for point in key_points[:3]:
            description_parts.append(f'• {point}')
        description_parts.append('')

    description_parts.append('the4thpath.com')
    description_parts.append('#Shorts')

    tags = CORNER_TAGS.get(corner, ['The4thPath']) + ['Shorts', 'AI']

    return {
        'snippet': {
            'title': f'{title} #Shorts',
            'description': '\n'.join(description_parts),
            'tags': tags,
            'categoryId': '28',  # Science & Technology
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False,
        },
    }


def publish_shorts(article: dict, video_path: str) -> bool:
    """
    쇼츠 MP4 → YouTube 업로드.
    video_path: shorts_converter.convert()가 생성한 MP4
    """
    if not Path(video_path).exists():
        logger.error(f"영상 파일 없음: {video_path}")
        return False

    logger.info(f"YouTube 쇼츠 발행 시작: {article.get('title', '')}")

    creds = _get_credentials()
    if not creds:
        return False

    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        service = build('youtube', 'v3', credentials=creds)
        metadata = build_video_metadata(article)

        media = MediaFileUpload(
            video_path,
            mimetype='video/mp4',
            resumable=True,
            chunksize=5 * 1024 * 1024,  # 5MB chunks
        )

        request = service.videos().insert(
            part='snippet,status',
            body=metadata,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                logger.info(f"업로드 진행: {pct}%")

        video_id = response.get('id', '')
        video_url = f'https://www.youtube.com/shorts/{video_id}'
        logger.info(f"YouTube 쇼츠 발행 완료: {video_url}")

        _log_published(article, video_id, 'youtube_shorts', video_url)
        return True

    except Exception as e:
        logger.error(f"YouTube 업로드 실패: {e}")
        return False


def _log_published(article: dict, post_id: str, platform: str, url: str = ''):
    pub_dir = DATA_DIR / 'published'
    pub_dir.mkdir(exist_ok=True)
    from datetime import datetime
    record = {
        'platform': platform,
        'post_id': post_id,
        'url': url,
        'title': article.get('title', ''),
        'corner': article.get('corner', ''),
        'published_at': datetime.now().isoformat(),
    }
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{platform}_{post_id}.json"
    with open(pub_dir / filename, 'w', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    sample = {
        'title': 'ChatGPT 처음 쓰는 사람을 위한 완전 가이드',
        'meta': 'ChatGPT를 처음 쓰는 분을 위한 단계별 가이드',
        'slug': 'chatgpt-guide',
        'corner': '쉬운세상',
        'key_points': ['무료로 바로 시작', 'GPT-3.5로도 충분', '프롬프트가 핵심'],
    }
    meta = build_video_metadata(sample)
    import pprint
    pprint.pprint(meta)
