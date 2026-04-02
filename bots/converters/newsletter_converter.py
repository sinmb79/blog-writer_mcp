"""
뉴스레터 변환봇 (converters/newsletter_converter.py)
역할: 원본 마크다운 → 주간 뉴스레터 HTML 발췌 (LAYER 2)
- TITLE + META + KEY_POINTS 발췌
- 주간 단위로 모아서 뉴스레터 HTML 생성
출력: data/outputs/weekly_{date}_newsletter.html
Phase 3에서 Substack 등 연동 예정
"""
import json
import logging
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


def extract_newsletter_item(article: dict, blog_url: str = '') -> dict:
    """단일 글에서 뉴스레터용 발췌 추출"""
    return {
        'title': article.get('title', ''),
        'meta': article.get('meta', ''),
        'corner': article.get('corner', ''),
        'key_points': article.get('key_points', []),
        'url': blog_url or f"{BLOG_BASE_URL}/{article.get('slug', '')}",
        'extracted_at': datetime.now().isoformat(),
    }


def build_newsletter_html(items: list[dict], week_str: str = '') -> str:
    """주간 뉴스레터 HTML 생성"""
    if not week_str:
        week_str = datetime.now().strftime('%Y년 %m월 %d일 주간')

    article_blocks = []
    for item in items:
        points_html = ''.join(
            f'<li>{p}</li>' for p in item.get('key_points', [])
        )
        block = f"""
        <div style="margin-bottom:32px;padding-bottom:24px;border-bottom:1px solid #eee;">
          <p style="color:#c8a84e;font-size:12px;margin:0 0 4px;">{item.get('corner','')}</p>
          <h2 style="font-size:20px;margin:0 0 8px;">
            <a href="{item.get('url','')}" style="color:#1a1a1a;text-decoration:none;">{item.get('title','')}</a>
          </h2>
          <p style="color:#555;font-size:14px;margin:0 0 12px;">{item.get('meta','')}</p>
          <ul style="color:#333;font-size:14px;margin:0;padding-left:20px;">
            {points_html}
          </ul>
          <p style="margin:12px 0 0;">
            <a href="{item.get('url','')}" style="color:#c8a84e;font-size:13px;">전체 읽기 →</a>
          </p>
        </div>"""
        article_blocks.append(block)

    articles_html = '\n'.join(article_blocks)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <title>The 4th Path 주간 뉴스레터 — {week_str}</title>
</head>
<body style="font-family:'Noto Sans KR',sans-serif;max-width:600px;margin:0 auto;padding:20px;color:#1a1a1a;">
  <div style="background:#c8a84e;padding:24px;margin-bottom:32px;">
    <h1 style="color:#fff;margin:0;font-size:28px;">The 4th Path</h1>
    <p style="color:#fff5dc;margin:4px 0 0;font-size:14px;">{week_str} 뉴스레터</p>
  </div>

  {articles_html}

  <div style="margin-top:32px;padding-top:16px;border-top:2px solid #c8a84e;text-align:center;">
    <p style="color:#888;font-size:12px;">
      <a href="{BLOG_BASE_URL}" style="color:#c8a84e;">the4thpath.com</a> | by 22B Labs
    </p>
  </div>
</body>
</html>"""


def generate_weekly(articles: list[dict], urls: list[str] = None,
                    save_file: bool = True) -> str:
    """
    여러 글을 모아 주간 뉴스레터 HTML 생성.
    articles: article dict 리스트
    urls: 각 글의 발행 URL (없으면 slug로 생성)
    """
    logger.info(f"주간 뉴스레터 생성 시작: {len(articles)}개 글")

    items = []
    for i, article in enumerate(articles):
        url = (urls[i] if urls and i < len(urls) else '')
        items.append(extract_newsletter_item(article, url))

    week_str = datetime.now().strftime('%Y년 %m월 %d일')
    html = build_newsletter_html(items, week_str)

    if save_file:
        date_str = datetime.now().strftime('%Y%m%d')
        filename = f"weekly_{date_str}_newsletter.html"
        output_path = OUTPUT_DIR / filename
        output_path.write_text(html, encoding='utf-8')
        logger.info(f"뉴스레터 저장: {output_path}")

    logger.info("주간 뉴스레터 생성 완료")
    return html


if __name__ == '__main__':
    samples = [
        {
            'title': 'ChatGPT 처음 쓰는 사람을 위한 완전 가이드',
            'meta': 'ChatGPT를 처음 사용하는 분을 위한 단계별 가이드',
            'slug': 'chatgpt-guide',
            'corner': '쉬운세상',
            'key_points': ['무료로 바로 시작', 'GPT-3.5로도 충분', '프롬프트가 핵심'],
        },
        {
            'title': '개발자 생산성 10배 높이는 AI 도구 5선',
            'meta': '실제 사용해본 AI 개발 도구 정직한 리뷰',
            'slug': 'ai-dev-tools',
            'corner': '숨은보물',
            'key_points': ['Cursor로 코딩 속도 3배', 'Copilot과 차이점', '무료 플랜으로 충분'],
        },
    ]
    html = generate_weekly(samples)
    print(html[:500])
