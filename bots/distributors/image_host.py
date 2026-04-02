"""
이미지 호스팅 헬퍼 (distributors/image_host.py)
역할: 로컬 카드 이미지 → 공개 URL 변환

Instagram Graph API는 공개 URL이 필요하므로
카드 이미지를 외부에서 접근 가능한 URL로 변환한다.

지원 방식:
1. ImgBB (무료 API, 키 필요)          ← IMGBB_API_KEY 설정 시
2. Blogger 미디어 업로드 (기존 OAuth)  ← 기본값 (추가 비용 없음)
3. 로컬 HTTP 서버 (개발/테스트용)      ← LOCAL_IMAGE_SERVER=true 시
"""
import base64
import json
import logging
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / '.env')

BASE_DIR = Path(__file__).parent.parent.parent
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'distributor.log', encoding='utf-8'),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

IMGBB_API_KEY = os.getenv('IMGBB_API_KEY', '')
IMGBB_API_URL = 'https://api.imgbb.com/v1/upload'


# ─── 방식 1: ImgBB ────────────────────────────────────

def upload_to_imgbb(image_path: str, expiration: int = 0) -> str:
    """
    ImgBB에 이미지 업로드.
    expiration: 0=영구, 초 단위 만료 시간 (예: 86400=1일)
    Returns: 공개 URL 또는 ''
    """
    if not IMGBB_API_KEY:
        logger.debug("IMGBB_API_KEY 없음 — ImgBB 건너뜀")
        return ''

    try:
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        payload = {
            'key': IMGBB_API_KEY,
            'image': image_data,
        }
        if expiration > 0:
            payload['expiration'] = expiration

        resp = requests.post(IMGBB_API_URL, data=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        if result.get('success'):
            url = result['data']['url']
            logger.info(f"ImgBB 업로드 완료: {url}")
            return url
        else:
            logger.warning(f"ImgBB 오류: {result.get('error', {})}")
            return ''
    except Exception as e:
        logger.error(f"ImgBB 업로드 실패: {e}")
        return ''


# ─── 방식 2: Blogger 미디어 업로드 ───────────────────

def upload_to_blogger(image_path: str) -> str:
    """
    Blogger에 이미지를 첨부파일로 업로드 후 공개 URL 반환.
    기존 Google OAuth (token.json) 재사용.
    Returns: 공개 URL 또는 ''
    """
    try:
        import sys
        sys.path.insert(0, str(BASE_DIR / 'bots'))
        from publisher_bot import get_google_credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        blog_id = os.getenv('BLOG_MAIN_ID', '')
        if not blog_id:
            logger.warning("BLOG_MAIN_ID 없음")
            return ''

        creds = get_google_credentials()
        service = build('blogger', 'v3', credentials=creds)

        # Blogger API: 미디어 업로드 (pages나 posts에 이미지 첨부)
        # 참고: Blogger는 직접 미디어 API가 없으므로 임시 draft 포스트로 업로드
        media = MediaFileUpload(image_path, mimetype='image/png', resumable=True)

        # 임시 draft 포스트에 이미지 삽입 → URL 추출 → 포스트 삭제
        img_data = open(image_path, 'rb').read()
        img_b64 = base64.b64encode(img_data).decode()
        img_html = f'<img src="data:image/png;base64,{img_b64}" />'

        draft = service.posts().insert(
            blogId=blog_id,
            body={'title': '__img_upload__', 'content': img_html},
            isDraft=True,
        ).execute()

        post_url = draft.get('url', '')
        post_id = draft.get('id', '')

        # draft 삭제
        if post_id:
            service.posts().delete(blogId=blog_id, postId=post_id).execute()

        # base64 embedded는 직접 URL이 아니므로 ImgBB fallback 필요
        # Blogger는 외부 이미지 호스팅 역할을 하지 않음
        # → 실제 운영 시 ImgBB 또는 CDN 사용 권장
        logger.warning("Blogger 미디어 업로드: base64 방식은 인스타 공개 URL로 부적합. ImgBB 권장.")
        return ''

    except Exception as e:
        logger.error(f"Blogger 업로드 실패: {e}")
        return ''


# ─── 방식 3: 로컬 HTTP 서버 (개발용) ─────────────────

_local_server = None


def start_local_server(port: int = 8765) -> str:
    """
    로컬 HTTP 파일 서버 시작 (개발/테스트용).
    Returns: base URL (예: http://192.168.1.100:8765)
    """
    import socket
    import threading
    import http.server
    import functools

    global _local_server
    if _local_server:
        return _local_server

    outputs_dir = str(BASE_DIR / 'data' / 'outputs')
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=outputs_dir
    )
    server = http.server.HTTPServer(('0.0.0.0', port), handler)

    def run():
        server.serve_forever()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    # 로컬 IP 확인
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = '127.0.0.1'

    base_url = f'http://{local_ip}:{port}'
    _local_server = base_url
    logger.info(f"로컬 이미지 서버 시작: {base_url}")
    return base_url


def get_local_url(image_path: str, port: int = 8765) -> str:
    """로컬 서버 URL 반환 (개발/ngrok 사용 시)"""
    base_url = start_local_server(port)
    filename = Path(image_path).name
    return f'{base_url}/{filename}'


# ─── 메인 함수 ───────────────────────────────────────

def get_public_url(image_path: str) -> str:
    """
    이미지 파일 → 공개 URL 반환.
    우선순위: ImgBB → 로컬 서버(개발용)
    """
    if not Path(image_path).exists():
        logger.error(f"이미지 파일 없음: {image_path}")
        return ''

    # 1. ImgBB (API 키 있을 때)
    url = upload_to_imgbb(image_path, expiration=86400 * 7)  # 7일
    if url:
        return url

    # 2. 로컬 HTTP 서버 (ngrok 또는 내부망 테스트용)
    if os.getenv('LOCAL_IMAGE_SERVER', '').lower() == 'true':
        url = get_local_url(image_path)
        logger.warning(f"로컬 서버 URL 사용 (인터넷 접근 필요): {url}")
        return url

    logger.warning(
        "공개 URL 생성 불가. .env에 IMGBB_API_KEY를 설정하거나 "
        "LOCAL_IMAGE_SERVER=true로 설정하세요."
    )
    return ''


# ─── 비디오 호스팅 (릴스용) ──────────────────────────

_local_video_server = None


def start_local_video_server(port: int = 8766) -> str:
    """
    로컬 HTTP 파일 서버 시작 — 비디오(MP4) 전용.
    Returns: base URL (예: http://192.168.1.100:8766)
    """
    import socket
    import threading
    import http.server
    import functools

    global _local_video_server
    if _local_video_server:
        return _local_video_server

    outputs_dir = str(BASE_DIR / 'data' / 'outputs')
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=outputs_dir
    )
    server = http.server.HTTPServer(('0.0.0.0', port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = '127.0.0.1'

    base_url = f'http://{local_ip}:{port}'
    _local_video_server = base_url
    logger.info(f"로컬 비디오 서버 시작: {base_url}")
    return base_url


def get_public_video_url(video_path: str) -> str:
    """
    비디오 파일 → 공개 URL 반환 (Instagram Reels, TikTok 등).
    Instagram Reels API는 공개 접근 가능한 MP4 URL이 필요.

    우선순위:
    1. LOCAL_IMAGE_SERVER=true → 로컬 HTTP 서버 (Tailscale 외부 접속 필요)
    2. VIDEO_HOST_BASE_URL 환경변수 → 직접 지정한 CDN/서버 URL

    운영 환경에서는 Tailscale로 미니PC를 외부에서 접근하거나,
    Cloudflare Tunnel 등을 사용하세요.
    """
    if not Path(video_path).exists():
        logger.error(f"비디오 파일 없음: {video_path}")
        return ''

    # 1. 직접 지정한 CDN/서버 베이스 URL
    video_base = os.getenv('VIDEO_HOST_BASE_URL', '').rstrip('/')
    if video_base:
        filename = Path(video_path).name
        url = f'{video_base}/{filename}'
        logger.info(f"비디오 외부 URL: {url}")
        return url

    # 2. 로컬 HTTP 서버 (Tailscale/ngrok으로 외부 접근 가능한 경우)
    if os.getenv('LOCAL_IMAGE_SERVER', '').lower() == 'true':
        base_url = start_local_video_server()
        filename = Path(video_path).name
        url = f'{base_url}/{filename}'
        logger.warning(f"로컬 비디오 서버 URL (외부 접근 필요): {url}")
        return url

    logger.warning(
        "비디오 공개 URL 생성 불가. .env에 VIDEO_HOST_BASE_URL을 설정하거나 "
        "LOCAL_IMAGE_SERVER=true (Tailscale/ngrok)로 설정하세요."
    )
    return ''


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        url = get_public_url(sys.argv[1])
        print(f"공개 URL: {url}")
    else:
        print("사용법: python image_host.py <이미지경로>")
