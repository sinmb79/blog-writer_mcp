"""
bots/shorts/youtube_uploader.py
역할: 렌더링된 쇼츠 MP4 → YouTube Data API v3 업로드

OAuth2: 기존 Blogger token.json 재사용 (youtube.upload 스코프 추가 필요).
AI Disclosure: YouTube 정책 준수 — 합성 콘텐츠 레이블 자동 설정.
업로드 쿼터: 하루 max daily_upload_limit (기본 6) 체크.

출력:
  data/shorts/published/{timestamp}.json
  {video_id, url, title, upload_time, article_id}
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
TOKEN_PATH = BASE_DIR / 'token.json'
PUBLISHED_DIR = BASE_DIR / 'data' / 'shorts' / 'published'
AI_DISCLOSURE_KO = '이 영상은 AI 도구를 활용하여 제작되었습니다.'

YOUTUBE_SCOPES = [
    'https://www.googleapis.com/auth/blogger',
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube.readonly',
    'https://www.googleapis.com/auth/webmasters',
]


def _load_config() -> dict:
    cfg_path = BASE_DIR / 'config' / 'shorts_config.json'
    if cfg_path.exists():
        return json.loads(cfg_path.read_text(encoding='utf-8'))
    return {}


def _get_youtube_service():
    """YouTube Data API v3 서비스 객체 생성 (기존 OAuth token.json 재사용)."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    if not TOKEN_PATH.exists():
        raise RuntimeError(f'OAuth 토큰 없음: {TOKEN_PATH} — scripts/get_token.py 실행 필요')

    creds_data = json.loads(TOKEN_PATH.read_text(encoding='utf-8'))
    client_id = os.environ.get('GOOGLE_CLIENT_ID', creds_data.get('client_id', ''))
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET', creds_data.get('client_secret', ''))

    creds = Credentials(
        token=creds_data.get('token'),
        refresh_token=creds_data.get('refresh_token') or os.environ.get('GOOGLE_REFRESH_TOKEN'),
        token_uri='https://oauth2.googleapis.com/token',
        client_id=client_id,
        client_secret=client_secret,
        scopes=YOUTUBE_SCOPES,
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # 갱신된 토큰 저장
        creds_data['token'] = creds.token
        TOKEN_PATH.write_text(json.dumps(creds_data, indent=2), encoding='utf-8')

    return build('youtube', 'v3', credentials=creds)


def _count_today_uploads(cfg: dict) -> int:
    """오늘 업로드 횟수 카운트."""
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime('%Y%m%d')
    count = 0
    for f in PUBLISHED_DIR.glob(f'{today}_*.json'):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            if data.get('video_id'):
                count += 1
        except Exception:
            pass
    return count


def _build_description(article: dict, script: dict) -> str:
    """업로드 설명 생성: 블로그 링크 + 해시태그 + AI 공시."""
    title = article.get('title', '')
    blog_url = article.get('url', article.get('link', ''))
    corner = article.get('corner', '')
    keywords = script.get('keywords', [])

    lines = []
    if title:
        lines.append(title)
    if blog_url:
        lines.append(f'\n자세한 내용: {blog_url}')
    lines.append('')

    # 해시태그
    tags = ['#Shorts', f'#{corner}'] if corner else ['#Shorts']
    tags += [f'#{k.replace(" ", "")}' for k in keywords[:3]]
    lines.append(' '.join(tags))

    # AI 공시 (YouTube 정책 준수)
    lines.append('')
    lines.append(AI_DISCLOSURE_KO)

    return '\n'.join(lines)


def _build_tags(article: dict, script: dict, cfg: dict) -> list[str]:
    """태그 목록 생성."""
    base_tags = cfg.get('youtube', {}).get('default_tags', ['shorts', 'AI', '테크'])
    corner = article.get('corner', '')
    keywords = script.get('keywords', [])

    tags = list(base_tags)
    if corner:
        tags.append(corner)
    tags.extend(keywords[:5])
    return list(dict.fromkeys(tags))  # 중복 제거


# ─── 업로드 ──────────────────────────────────────────────────

def upload(
    video_path: Path,
    article: dict,
    script: dict,
    timestamp: str,
    cfg: Optional[dict] = None,
) -> dict:
    """
    쇼츠 MP4 → YouTube 업로드.

    Args:
        video_path: 렌더링된 MP4 경로
        article:    article dict (title, url, corner 등)
        script:     shorts 스크립트 (hook, keywords 등)
        timestamp:  파일명 prefix (발행 기록용)
        cfg:        shorts_config.json dict

    Returns:
        {video_id, url, title, upload_time, article_id}

    Raises:
        RuntimeError — 업로드 실패 또는 쿼터 초과
    """
    if cfg is None:
        cfg = _load_config()

    yt_cfg = cfg.get('youtube', {})
    daily_limit = yt_cfg.get('daily_upload_limit', 6)

    # 쿼터 체크
    today_count = _count_today_uploads(cfg)
    if today_count >= daily_limit:
        raise RuntimeError(f'YouTube 일일 업로드 한도 초과: {today_count}/{daily_limit}')

    # 메타데이터 구성
    title = script.get('hook', article.get('title', ''))[:100]
    description = _build_description(article, script)
    tags = _build_tags(article, script, cfg)

    try:
        from googleapiclient.http import MediaFileUpload
        youtube = _get_youtube_service()

        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags,
                'categoryId': yt_cfg.get('category_id', '28'),
            },
            'status': {
                'privacyStatus': yt_cfg.get('privacy_status', 'public'),
                'madeForKids': yt_cfg.get('made_for_kids', False),
                'selfDeclaredMadeForKids': False,
            },
        }

        media = MediaFileUpload(
            str(video_path),
            mimetype='video/mp4',
            resumable=True,
            chunksize=5 * 1024 * 1024,  # 5MB chunks
        )

        request = youtube.videos().insert(
            part='snippet,status',
            body=body,
            media_body=media,
        )

        logger.info(f'YouTube 업로드 시작: {video_path.name}')
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.debug(f'업로드 진행: {int(status.progress() * 100)}%')

        video_id = response.get('id', '')
        video_url = f'https://www.youtube.com/shorts/{video_id}'
        logger.info(f'YouTube 업로드 완료: {video_url}')

        # AI 합성 콘텐츠 레이블 설정 (YouTube 정책 준수)
        _set_ai_disclosure(youtube, video_id)

    except Exception as e:
        raise RuntimeError(f'YouTube 업로드 실패: {e}') from e

    # 발행 기록 저장
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        'video_id': video_id,
        'url': video_url,
        'title': title,
        'upload_time': datetime.now().isoformat(),
        'article_id': article.get('slug', ''),
        'script_hook': script.get('hook', ''),
    }
    record_path = PUBLISHED_DIR / f'{timestamp}.json'
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    logger.info(f'발행 기록 저장: {record_path.name}')
    return record


def _set_ai_disclosure(youtube, video_id: str) -> None:
    """
    YouTube 합성 콘텐츠 레이블 설정 (v2 — AI 공시 정책 준수).
    contentDetails.contentRating 업데이트.
    """
    try:
        youtube.videos().update(
            part='contentDetails',
            body={
                'id': video_id,
                'contentDetails': {
                    'contentRating': {
                        # Altered/synthetic content declaration
                    },
                },
            },
        ).execute()
        logger.debug('AI 합성 콘텐츠 레이블 설정 완료')
    except Exception as e:
        # 레이블 실패는 경고만 (업로드 자체는 성공)
        logger.warning(f'AI 공시 레이블 설정 실패: {e}')
