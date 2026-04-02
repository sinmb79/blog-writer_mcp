"""
링크봇 (linker_bot.py)
역할: 글 본문에 쿠팡 파트너스 링크와 어필리에이트 링크 자동 삽입
"""
import hashlib
import hmac
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / '.env')

BASE_DIR = Path(__file__).parent.parent
CONFIG_DIR = BASE_DIR / 'config'
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'linker.log', encoding='utf-8'),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

COUPANG_ACCESS_KEY = os.getenv('COUPANG_ACCESS_KEY', '')
COUPANG_SECRET_KEY = os.getenv('COUPANG_SECRET_KEY', '')
COUPANG_API_BASE = 'https://api-gateway.coupang.com'


def load_config(filename: str) -> dict:
    with open(CONFIG_DIR / filename, 'r', encoding='utf-8') as f:
        return json.load(f)


# ─── 쿠팡 파트너스 API ────────────────────────────────

def _generate_coupang_hmac(method: str, url: str, query: str) -> dict:
    """쿠팡 HMAC 서명 생성"""
    datetime_str = datetime.now(timezone.utc).strftime('%y%m%dT%H%M%SZ')
    path = url.split(COUPANG_API_BASE)[-1].split('?')[0]
    message = datetime_str + method + path + query
    signature = hmac.new(
        COUPANG_SECRET_KEY.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return {
        'Authorization': f'CEA algorithm=HmacSHA256, access-key={COUPANG_ACCESS_KEY}, '
                         f'signed-date={datetime_str}, signature={signature}',
        'Content-Type': 'application/json;charset=UTF-8',
    }


def search_coupang_products(keyword: str, limit: int = 3) -> list[dict]:
    """쿠팡 파트너스 API로 상품 검색"""
    if not COUPANG_ACCESS_KEY or not COUPANG_SECRET_KEY:
        logger.warning("쿠팡 API 키 없음 — 링크 삽입 건너뜀")
        return []

    path = '/v2/providers/affiliate_api/apis/openapi/products/search'
    params = {
        'keyword': keyword,
        'limit': limit,
        'subId': 'blog-writer',
    }
    query_string = urlencode(params)
    url = f'{COUPANG_API_BASE}{path}?{query_string}'

    try:
        headers = _generate_coupang_hmac('GET', url, query_string)
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        products = data.get('data', {}).get('productData', [])
        return [
            {
                'name': p.get('productName', keyword),
                'price': p.get('productPrice', 0),
                'url': p.get('productUrl', ''),
                'image': p.get('productImage', ''),
            }
            for p in products[:limit]
        ]
    except Exception as e:
        logger.warning(f"쿠팡 API 오류 ({keyword}): {e}")
        return []


def build_coupang_link_html(product: dict) -> str:
    """쿠팡 상품 링크 HTML 생성"""
    name = product.get('name', '')
    url = product.get('url', '')
    price = product.get('price', 0)
    price_str = f"{int(price):,}원" if price else ''
    return (
        f'<p class="coupang-link">'
        f'🛒 <a href="{url}" target="_blank" rel="nofollow">{name}</a>'
        f'{" — " + price_str if price_str else ""}'
        f'</p>\n'
    )


# ─── 본문 링크 삽입 ──────────────────────────────────

def insert_links_into_html(html_content: str, coupang_keywords: list[str],
                            fixed_links: list[dict]) -> str:
    """HTML 본문에 쿠팡 링크와 고정 링크 삽입"""
    soup = BeautifulSoup(html_content, 'lxml')

    # 고정 링크 (키워드 텍스트가 본문에 있으면 첫 번째 등장 위치에 링크)
    for fixed in fixed_links:
        kw = fixed.get('keyword', '')
        link_url = fixed.get('url', '')
        label = fixed.get('label', kw)
        if not kw or not link_url:
            continue
        for p in soup.find_all(['p', 'li']):
            text = p.get_text()
            if kw in text:
                # 이미 링크가 있으면 건너뜀
                if p.find('a', string=re.compile(re.escape(kw))):
                    break
                new_html = p.decode_contents().replace(
                    kw,
                    f'<a href="{link_url}" target="_blank">{kw}</a>',
                    1
                )
                p.clear()
                p.append(BeautifulSoup(new_html, 'lxml'))
                break

    # 쿠팡 링크: 결론/추천 섹션 앞에 상품 박스 삽입
    if coupang_keywords and (COUPANG_ACCESS_KEY and COUPANG_SECRET_KEY):
        coupang_block_parts = []
        for kw in coupang_keywords[:3]:  # 최대 3개 키워드
            products = search_coupang_products(kw, limit=2)
            for product in products:
                coupang_block_parts.append(build_coupang_link_html(product))

        if coupang_block_parts:
            coupang_block_html = (
                '<div class="coupang-products">\n'
                '<p><strong>관련 상품 추천</strong></p>\n'
                + ''.join(coupang_block_parts) +
                '</div>\n'
            )
            # 결론 H2 앞에 삽입
            for h2 in soup.find_all('h2'):
                if any(kw in h2.get_text() for kw in ['결론', '마무리', '정리', '요약']):
                    block = BeautifulSoup(coupang_block_html, 'lxml')
                    h2.insert_before(block)
                    break
            else:
                # 결론 섹션 없으면 본문 끝에 추가
                body_tag = soup.find('body') or soup
                block = BeautifulSoup(coupang_block_html, 'lxml')
                body_tag.append(block)

    return str(soup)


def add_disclaimer(html_content: str, disclaimer_text: str) -> str:
    """쿠팡 필수 면책 문구 추가 (이미 있으면 건너뜀)"""
    if disclaimer_text in html_content:
        return html_content
    disclaimer_html = (
        f'\n<hr/>\n'
        f'<p class="affiliate-disclaimer"><small>⚠️ {disclaimer_text}</small></p>\n'
    )
    return html_content + disclaimer_html


# ─── 메인 함수 ───────────────────────────────────────

def process(article: dict, html_content: str) -> str:
    """
    링크봇 메인: HTML 본문에 쿠팡/어필리에이트 링크 삽입 후 반환
    """
    logger.info(f"링크 삽입 시작: {article.get('title', '')}")
    affiliate_cfg = load_config('affiliate_links.json')

    coupang_keywords = article.get('coupang_keywords', [])
    fixed_links = affiliate_cfg.get('fixed_links', [])
    disclaimer_text = affiliate_cfg.get('disclaimer_text', '')

    # 링크 삽입
    html_content = insert_links_into_html(html_content, coupang_keywords, fixed_links)

    # 쿠팡 키워드가 있으면 면책 문구 추가
    if coupang_keywords and disclaimer_text:
        html_content = add_disclaimer(html_content, disclaimer_text)

    logger.info("링크 삽입 완료")
    return html_content


if __name__ == '__main__':
    sample_html = '''
    <h2>ChatGPT 소개</h2>
    <p>ChatGPT Plus를 사용하면 더 빠른 응답을 받을 수 있습니다.</p>
    <h2>키보드 추천</h2>
    <p>좋은 키보드는 생산성을 높입니다.</p>
    <h2>결론</h2>
    <p>AI 도구를 잘 활용하세요.</p>
    '''
    sample_article = {
        'title': '테스트 글',
        'coupang_keywords': ['키보드', '마우스'],
    }
    result = process(sample_article, sample_html)
    print(result[:500])
