"""
블로그 변환봇 (converters/blog_converter.py)
역할: 원본 마크다운 → 블로그 HTML 변환 (LAYER 2)
- 마크다운 → HTML (목차, 테이블, 코드블록)
- AdSense 플레이스홀더 삽입
- Schema.org Article JSON-LD
- 쿠팡 링크봇 호출
출력: data/outputs/{date}_{slug}_blog.html
"""
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import markdown
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR / 'bots'))

LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)
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


def markdown_to_html(md_text: str) -> tuple[str, str]:
    """마크다운 → HTML (목차 포함)"""
    md = markdown.Markdown(
        extensions=['toc', 'tables', 'fenced_code', 'attr_list'],
        extension_configs={
            'toc': {'title': '목차', 'toc_depth': '2-3'}
        }
    )
    html = md.convert(md_text)
    toc = md.toc
    return html, toc


def insert_adsense_placeholders(html: str) -> str:
    """두 번째 H2 뒤 + 결론 H2 앞에 AdSense 슬롯 삽입"""
    AD_SLOT_1 = '\n<!-- AD_SLOT_1 -->\n'
    AD_SLOT_2 = '\n<!-- AD_SLOT_2 -->\n'
    soup = BeautifulSoup(html, 'lxml')
    h2_tags = soup.find_all('h2')

    if len(h2_tags) >= 2:
        ad_tag = BeautifulSoup(AD_SLOT_1, 'html.parser')
        h2_tags[1].insert_after(ad_tag)

    for h2 in soup.find_all('h2'):
        if any(kw in h2.get_text() for kw in ['결론', '마무리', '정리', '요약', 'conclusion']):
            ad_tag2 = BeautifulSoup(AD_SLOT_2, 'html.parser')
            h2.insert_before(ad_tag2)
            break

    return str(soup)


def build_json_ld(article: dict, post_url: str = '') -> str:
    """Schema.org Article JSON-LD"""
    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": article.get('title', ''),
        "description": article.get('meta', ''),
        "datePublished": datetime.now(timezone.utc).isoformat(),
        "dateModified": datetime.now(timezone.utc).isoformat(),
        "author": {"@type": "Person", "name": "테크인사이더"},
        "publisher": {
            "@type": "Organization",
            "name": "The 4th Path",
            "logo": {"@type": "ImageObject", "url": f"{BLOG_BASE_URL}/logo.png"}
        },
        "mainEntityOfPage": {"@type": "WebPage", "@id": post_url or BLOG_BASE_URL},
    }
    return f'<script type="application/ld+json">\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n</script>'


def build_full_html(article: dict, body_html: str, toc_html: str,
                    post_url: str = '') -> str:
    """JSON-LD + 목차 + 본문 + 면책 조합"""
    json_ld = build_json_ld(article, post_url)
    disclaimer = article.get('disclaimer', '')
    parts = [json_ld]
    if toc_html:
        parts.append(f'<div class="toc-wrapper">{toc_html}</div>')
    parts.append(body_html)
    if disclaimer:
        parts.append(f'<hr/><p class="disclaimer"><small>{disclaimer}</small></p>')
    return '\n'.join(parts)


def _is_html_body(body: str) -> bool:
    """AI가 이미 HTML을 출력했는지 감지 (마크다운 변환 건너뜀)"""
    stripped = body.lstrip()
    return stripped.startswith('<') and any(
        tag in stripped[:200].lower()
        for tag in ['<style', '<div', '<h1', '<section', '<article', '<p>']
    )


def convert(article: dict, save_file: bool = True) -> str:
    """
    article dict → 블로그 HTML 문자열 반환.
    save_file=True이면 data/outputs/에 저장.
    BODY가 이미 HTML이면 마크다운 변환을 건너뜀.
    """
    logger.info(f"블로그 변환 시작: {article.get('title', '')}")

    body = article.get('body', '')

    if _is_html_body(body):
        # AI가 Blogger-ready HTML을 직접 출력한 경우 — 변환 없이 그대로 사용
        logger.info("HTML 본문 감지 — 마크다운 변환 건너뜀")
        body_html = body
        toc_html = ''
    else:
        # 레거시 마크다운 → HTML 변환
        body_html, toc_html = markdown_to_html(body)

    # AdSense 삽입
    body_html = insert_adsense_placeholders(body_html)

    # 쿠팡 링크 삽입
    try:
        import linker_bot
        body_html = linker_bot.process(article, body_html)
    except Exception as e:
        logger.warning(f"쿠팡 링크 삽입 실패 (건너뜀): {e}")

    # 최종 HTML
    html = build_full_html(article, body_html, toc_html)

    if save_file:
        slug = article.get('slug', 'article')
        date_str = datetime.now().strftime('%Y%m%d')
        filename = f"{date_str}_{slug}_blog.html"
        output_path = OUTPUT_DIR / filename
        output_path.write_text(html, encoding='utf-8')
        logger.info(f"저장: {output_path}")

    logger.info("블로그 변환 완료")
    return html


if __name__ == '__main__':
    sample = {
        'title': '테스트 글',
        'meta': '테스트 설명',
        'slug': 'test-article',
        'corner': '쉬운세상',
        'body': '## 소개\n\n본문입니다.\n\n## 결론\n\n마무리입니다.',
        'coupang_keywords': [],
        'disclaimer': '',
        'key_points': ['포인트 1', '포인트 2', '포인트 3'],
    }
    html = convert(sample)
    print(html[:500])
