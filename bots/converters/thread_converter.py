# The 4th Path: ⟨H⊕A⟩ ↦ Ω
# Human × AI → a better world.
# 22B Labs | the4thpath.com
"""
X 스레드 변환봇 (converters/thread_converter.py)
역할: 원본 마크다운 → X(트위터) 스레드 JSON (LAYER 2)
- TITLE + KEY_POINTS → 280자 트윗 3-5개로 분할
- 첫 트윗: 흥미 유발 + 코너 해시태그
- 중간 트윗: 핵심 포인트
- 마지막 트윗: 블로그 링크 + CTA
출력: data/outputs/{date}_{slug}_thread.json
"""
import json
import logging
import textwrap
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
LOG_DIR = BASE_DIR / 'logs'
OUTPUT_DIR = BASE_DIR / 'data' / 'outputs'
OUTPUT_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'converter.log', encoding='utf-8'),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

BLOG_BASE_URL = 'https://the4thpath.com'
TWEET_MAX = 280

CORNER_HASHTAGS = {
    '쉬운세상': '#쉬운세상 #AI활용 #디지털라이프',
    '숨은보물': '#숨은보물 #AI도구 #생산성',
    '바이브리포트': '#바이브리포트 #트렌드 #AI시대',
    '팩트체크': '#팩트체크 #AI뉴스',
    '한컷': '#한컷 #AI만평',
}

BRAND_TAG = '#The4thPath'
BRAND_NAME = 'The 4th Path'
BRAND_SITE = 'the4thpath.com'


def _split_to_tweet(text: str, max_len: int = TWEET_MAX) -> list[str]:
    """텍스트를 280자 단위로 자연스럽게 분할"""
    if len(text) <= max_len:
        return [text]

    tweets = []
    sentences = text.replace('. ', '.\n').replace('다. ', '다.\n').split('\n')
    current = ''
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        test = (current + ' ' + sentence).strip() if current else sentence
        if len(test) <= max_len:
            current = test
        else:
            if current:
                tweets.append(current)
            # 문장 자체가 너무 길면 강제 분할
            if len(sentence) > max_len:
                chunks = textwrap.wrap(sentence, max_len - 5)
                tweets.extend(chunks[:-1])
                current = chunks[-1] if chunks else ''
            else:
                current = sentence
    if current:
        tweets.append(current)
    return tweets or [text[:max_len]]


def convert(article: dict, blog_url: str = '', save_file: bool = True) -> list[dict]:
    """
    article dict → X 스레드 트윗 리스트.
    각 트윗: {'order': int, 'text': str, 'char_count': int}
    """
    title = article.get('title', '')
    corner = article.get('corner', '')
    key_points = article.get('key_points', [])
    tags = article.get('tags', [])
    slug = article.get('slug', 'article')

    logger.info(f"스레드 변환 시작: {title}")

    hashtags = CORNER_HASHTAGS.get(corner, '')
    tag_str = ' '.join(f'#{t}' for t in tags[:3] if t)
    if tag_str:
        hashtags = hashtags + ' ' + tag_str

    tweets = []

    # 트윗 1: 흥미 유발 + 제목 + 코너 해시태그
    intro_text = f"👀 {title}\n\n{hashtags} {BRAND_TAG}\n{BRAND_NAME}"
    if len(intro_text) <= TWEET_MAX:
        tweets.append(intro_text)
    else:
        short_title = textwrap.shorten(title, width=100, placeholder='...')
        tweets.append(f"👀 {short_title}\n\n{hashtags}\n{BRAND_NAME}")

    # 트윗 2-4: 핵심 포인트
    for i, point in enumerate(key_points[:3], 1):
        bullets = ['①', '②', '③']
        bullet = bullets[i - 1] if i <= 3 else f'{i}.'
        tweet_text = f"{bullet} {point}"
        if len(tweet_text) <= TWEET_MAX:
            tweets.append(tweet_text)
        else:
            split_tweets = _split_to_tweet(tweet_text)
            tweets.extend(split_tweets)

    # 마지막 트윗: CTA + 블로그 링크
    post_url = blog_url or f"{BLOG_BASE_URL}/{slug}"
    cta_text = (
        f"전체 내용 보기 👇\n{post_url}\n\n"
        f"{BRAND_NAME} | {BRAND_SITE}\n"
        f"Human × AI → a better world.\n"
        f"{BRAND_TAG}"
    )
    tweets.append(cta_text)

    result = [
        {'order': i + 1, 'text': t, 'char_count': len(t)}
        for i, t in enumerate(tweets)
    ]

    if save_file:
        date_str = datetime.now().strftime('%Y%m%d')
        filename = f"{date_str}_{slug}_thread.json"
        output_path = OUTPUT_DIR / filename
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        logger.info(f"스레드 저장: {output_path} ({len(result)}개 트윗)")

    logger.info("스레드 변환 완료")
    return result


if __name__ == '__main__':
    sample = {
        'title': 'ChatGPT 처음 쓰는 사람을 위한 완전 가이드',
        'slug': 'chatgpt-guide',
        'corner': '쉬운세상',
        'tags': ['ChatGPT', 'AI', '가이드'],
        'key_points': [
            '무료로 바로 시작할 수 있다 — chat.openai.com 접속',
            'GPT-4는 유료지만 GPT-3.5도 일반 용도엔 충분하다',
            '프롬프트의 질이 답변의 질을 결정한다',
        ],
    }
    threads = convert(sample)
    for t in threads:
        print(f"[{t['order']}] ({t['char_count']}자) {t['text']}")
        print()
