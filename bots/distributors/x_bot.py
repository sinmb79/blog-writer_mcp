"""
X(트위터) 배포봇 (distributors/x_bot.py)
역할: X 스레드 JSON → X API v2로 순차 트윗 게시 (LAYER 3)

사전 조건:
- X Developer 계정 + 앱 등록
- .env: X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET
"""
import json
import logging
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from requests_oauthlib import OAuth1

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

X_API_KEY = os.getenv('X_API_KEY', '')
X_API_SECRET = os.getenv('X_API_SECRET', '')
X_ACCESS_TOKEN = os.getenv('X_ACCESS_TOKEN', '')
X_ACCESS_SECRET = os.getenv('X_ACCESS_SECRET', '')

X_API_V2 = 'https://api.twitter.com/2/tweets'


def _check_credentials() -> bool:
    if not all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET]):
        logger.warning("X API 자격증명 없음 (.env: X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET)")
        return False
    return True


def _get_auth() -> OAuth1:
    return OAuth1(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET)


def post_tweet(text: str, reply_to_id: str = '') -> str:
    """
    단일 트윗 게시.
    reply_to_id: 스레드 연결용 이전 트윗 ID
    Returns: 트윗 ID
    """
    if not _check_credentials():
        return ''

    payload = {'text': text}
    if reply_to_id:
        payload['reply'] = {'in_reply_to_tweet_id': reply_to_id}

    try:
        auth = _get_auth()
        resp = requests.post(X_API_V2, json=payload, auth=auth, timeout=15)
        resp.raise_for_status()
        tweet_id = resp.json().get('data', {}).get('id', '')
        logger.info(f"트윗 게시: {tweet_id} ({len(text)}자)")
        return tweet_id
    except Exception as e:
        logger.error(f"트윗 게시 실패: {e}")
        return ''


def publish_thread(article: dict, thread_data: list[dict]) -> bool:
    """
    스레드 JSON → 순차 트윗 게시.
    thread_data: thread_converter.convert() 반환값
    """
    if not _check_credentials():
        logger.info("X API 미설정 — 발행 건너뜀")
        return False

    title = article.get('title', '')
    logger.info(f"X 스레드 발행 시작: {title} ({len(thread_data)}개 트윗)")

    prev_id = ''
    tweet_ids = []
    for tweet in sorted(thread_data, key=lambda x: x['order']):
        text = tweet['text']
        tweet_id = post_tweet(text, prev_id)
        if not tweet_id:
            logger.error(f"스레드 중단: {tweet['order']}번 트윗 실패")
            return False
        tweet_ids.append(tweet_id)
        prev_id = tweet_id
        time.sleep(1)  # rate limit 방지

    logger.info(f"X 스레드 발행 완료: {len(tweet_ids)}개")
    _log_published(article, tweet_ids[0] if tweet_ids else '', 'x_thread')
    return True


def publish_thread_from_file(article: dict, thread_file: str) -> bool:
    """파일에서 스레드 데이터 로드 후 게시"""
    try:
        data = json.loads(Path(thread_file).read_text(encoding='utf-8'))
        return publish_thread(article, data)
    except Exception as e:
        logger.error(f"스레드 파일 로드 실패: {e}")
        return False


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
    import sys
    sys.path.insert(0, str(BASE_DIR / 'bots' / 'converters'))
    import thread_converter

    sample = {
        'title': 'ChatGPT 처음 쓰는 사람을 위한 완전 가이드',
        'slug': 'chatgpt-guide',
        'corner': '쉬운세상',
        'tags': ['ChatGPT', 'AI'],
        'key_points': ['무료로 바로 시작', 'GPT-3.5로도 충분', '프롬프트가 핵심'],
    }
    threads = thread_converter.convert(sample, save_file=False)
    for t in threads:
        print(f"[{t['order']}] {t['text']}\n")
