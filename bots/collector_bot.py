"""
수집봇 (collector_bot.py)
역할: 트렌드/도구/사례 수집 + 품질 점수 계산 + 폐기 규칙 적용
실행: 매일 07:00 (스케줄러 호출)
"""
import json
import logging
import os
import re
import hashlib
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / '.env')

BASE_DIR = Path(__file__).parent.parent
CONFIG_DIR = BASE_DIR / 'config'
DATA_DIR = BASE_DIR / 'data'
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'collector.log', encoding='utf-8'),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

# 코너별 타입
CORNER_TYPES = {
    'easy_guide': '쉬운세상',
    'hidden_gems': '숨은보물',
    'vibe_report': '바이브리포트',
    'fact_check': '팩트체크',
    'one_cut': '한컷',
}

# 글감 타입 비율: 에버그린 50%, 트렌드 30%, 개성 20%
TOPIC_RATIO = {'evergreen': 0.5, 'trending': 0.3, 'personality': 0.2}


def load_config(filename: str) -> dict:
    with open(CONFIG_DIR / filename, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_published_titles() -> list[str]:
    """발행 이력에서 제목 목록을 불러옴 (유사도 비교용)"""
    titles = []
    published_dir = DATA_DIR / 'published'
    for f in published_dir.glob('*.json'):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            if 'title' in data:
                titles.append(data['title'])
        except Exception:
            pass
    return titles


def title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def is_duplicate(title: str, published_titles: list[str], threshold: float = 0.8) -> bool:
    for pub_title in published_titles:
        if title_similarity(title, pub_title) >= threshold:
            return True
    return False


def calc_freshness_score(published_at: datetime | None, max_score: int = 20) -> int:
    """발행 시간 기준 신선도 점수 (24h 이내 만점, 7일 초과 0점)"""
    if published_at is None:
        return max_score // 2
    now = datetime.now(timezone.utc)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    age_hours = (now - published_at).total_seconds() / 3600
    if age_hours <= 24:
        return max_score
    elif age_hours >= 168:
        return 0
    else:
        ratio = 1 - (age_hours - 24) / (168 - 24)
        return int(max_score * ratio)


def calc_korean_relevance(text: str, rules: dict) -> int:
    """한국 독자 관련성 점수"""
    max_score = rules['scoring']['korean_relevance']['max']
    keywords = rules['scoring']['korean_relevance']['keywords']

    # 한국어 문자(가-힣) 비율 체크 — 한국어 콘텐츠 자체에 기본점수 부여
    korean_chars = sum(1 for c in text if '\uac00' <= c <= '\ud7a3')
    korean_ratio = korean_chars / max(len(text), 1)
    if korean_ratio >= 0.15:
        base = 15  # 한국어 텍스트면 기본 15점
    elif korean_ratio >= 0.05:
        base = 8
    else:
        base = 0

    # 브랜드/지역 키워드 보너스
    matched = sum(1 for kw in keywords if kw in text)
    bonus = min(matched * 5, max_score - base)

    return min(base + bonus, max_score)


def calc_source_trust(source_url: str, rules: dict) -> tuple[int, str]:
    """출처 신뢰도 점수 + 레벨"""
    trust_cfg = rules['scoring']['source_trust']
    high_src = trust_cfg.get('high_sources', [])
    low_src = trust_cfg.get('low_sources', [])
    url_lower = source_url.lower()
    for s in low_src:
        if s in url_lower:
            return trust_cfg['levels']['low'], 'low'
    for s in high_src:
        if s in url_lower:
            return trust_cfg['levels']['high'], 'high'
    return trust_cfg['levels']['medium'], 'medium'


def calc_monetization(text: str, rules: dict) -> int:
    """수익 연결 가능성 점수"""
    keywords = rules['scoring']['monetization']['keywords']
    matched = sum(1 for kw in keywords if kw in text)
    return min(matched * 5, rules['scoring']['monetization']['max'])


def is_evergreen(title: str, rules: dict) -> bool:
    evergreen_kws = rules.get('evergreen_keywords', [])
    return any(kw in title for kw in evergreen_kws)


def apply_discard_rules(item: dict, rules: dict, published_titles: list[str]) -> str | None:
    """
    폐기 규칙 적용. 폐기 사유 반환(None이면 통과).
    """
    title = item.get('topic', '')
    text = title + ' ' + item.get('description', '')
    discard_rules = rules.get('discard_rules', [])

    for rule in discard_rules:
        rule_id = rule['id']

        if rule_id == 'no_korean_relevance':
            if item.get('korean_relevance_score', 0) == 0:
                return '한국 독자 관련성 없음'

        elif rule_id == 'unverified_source':
            if item.get('source_trust_level') == 'unknown':
                return '출처 불명'

        elif rule_id == 'duplicate_topic':
            threshold = rule.get('similarity_threshold', 0.8)
            if is_duplicate(title, published_titles, threshold):
                return f'기발행 주제와 유사도 {threshold*100:.0f}% 이상'

        elif rule_id == 'stale_trend':
            if not item.get('is_evergreen', False):
                max_days = rule.get('max_age_days', 7)
                pub_at = item.get('published_at')
                if pub_at:
                    if isinstance(pub_at, str):
                        try:
                            pub_at = datetime.fromisoformat(pub_at)
                        except Exception:
                            pub_at = None
                    if pub_at:
                        if pub_at.tzinfo is None:
                            pub_at = pub_at.replace(tzinfo=timezone.utc)
                        age_days = (datetime.now(timezone.utc) - pub_at).days
                        if age_days > max_days:
                            return f'{age_days}일 지난 트렌드'

        elif rule_id == 'promotional':
            kws = rule.get('keywords', [])
            if any(kw in text for kw in kws):
                return '광고성/홍보성 콘텐츠'

        elif rule_id == 'clickbait':
            patterns = rule.get('patterns', [])
            if any(p in text for p in patterns):
                return '클릭베이트성 주제'

    return None


def assign_corner(item: dict, topic_type: str) -> str:
    """글감에 코너 배정"""
    title = item.get('topic', '').lower()
    source = item.get('source', 'rss').lower()

    if topic_type == 'evergreen':
        if any(kw in title for kw in ['가이드', '방법', '사용법', '입문', '튜토리얼', '기초']):
            return '쉬운세상'
        return '숨은보물'
    elif topic_type == 'trending':
        if source in ['github', 'product_hunt']:
            return '숨은보물'
        return '쉬운세상'
    else:  # personality
        return '바이브리포트'


def calculate_quality_score(item: dict, rules: dict) -> int:
    """0-100점 품질 점수 계산"""
    text = item.get('topic', '') + ' ' + item.get('description', '')
    source_url = item.get('source_url', '')
    pub_at_str = item.get('published_at')
    pub_at = None
    if pub_at_str:
        try:
            pub_at = datetime.fromisoformat(pub_at_str)
        except Exception:
            pass

    kr_score = calc_korean_relevance(text, rules)
    fresh_score = calc_freshness_score(pub_at)
    # search_demand: pytrends 연동 후 실제값 사용 (RSS 기본값 12)
    search_score = item.get('search_demand_score', 12)
    # 신뢰도: _trust_override 이미 설정된 경우 우선 사용
    if '_trust_score' in item:
        trust_score = item['_trust_score']
        trust_level = item.get('source_trust_level', 'medium')
    else:
        trust_score, trust_level = calc_source_trust(source_url, rules)
    mono_score = calc_monetization(text, rules)

    item['korean_relevance_score'] = kr_score
    item['source_trust_level'] = trust_level
    item['is_evergreen'] = is_evergreen(item.get('topic', ''), rules)

    total = kr_score + fresh_score + search_score + trust_score + mono_score
    return min(total, 100)


# ─── 수집 소스별 함수 ─────────────────────────────────

def collect_google_trends() -> list[dict]:
    """Google Trends (pytrends) — 한국 일간 트렌딩"""
    items = []
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl='ko', tz=540, timeout=(10, 30))
        trending_df = pytrends.trending_searches(pn='south_korea')
        for keyword in trending_df[0].tolist()[:20]:
            items.append({
                'topic': keyword,
                'description': f'Google Trends 한국 트렌딩 키워드: {keyword}',
                'source': 'google_trends',
                'source_url': f'https://trends.google.co.kr/trends/explore?q={keyword}&geo=KR',
                'published_at': datetime.now(timezone.utc).isoformat(),
                'search_demand_score': 15,
                'topic_type': 'trending',
            })
    except Exception as e:
        logger.warning(f"Google Trends 수집 실패: {e}")
    return items


def collect_github_trending(sources_cfg: dict) -> list[dict]:
    """GitHub Trending 크롤링"""
    items = []
    cfg = sources_cfg.get('github_trending', {})
    languages = cfg.get('languages', [''])
    since = cfg.get('since', 'daily')

    for lang in languages:
        url = f"https://github.com/trending/{lang}?since={since}"
        try:
            resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
            soup = BeautifulSoup(resp.text, 'lxml')
            repos = soup.select('article.Box-row')
            for repo in repos[:10]:
                name_el = repo.select_one('h2 a')
                desc_el = repo.select_one('p')
                stars_el = repo.select_one('a[href*="stargazers"]')
                if not name_el:
                    continue
                repo_path = name_el.get('href', '').strip('/')
                topic = repo_path.replace('/', ' / ')
                desc = desc_el.get_text(strip=True) if desc_el else ''
                stars = stars_el.get_text(strip=True) if stars_el else '0'
                items.append({
                    'topic': topic,
                    'description': desc,
                    'source': 'github',
                    'source_url': f'https://github.com/{repo_path}',
                    'published_at': datetime.now(timezone.utc).isoformat(),
                    'search_demand_score': 12,
                    'topic_type': 'trending',
                    'extra': {'stars': stars},
                })
        except Exception as e:
            logger.warning(f"GitHub Trending 수집 실패 ({lang}): {e}")
    return items


def collect_hacker_news(sources_cfg: dict) -> list[dict]:
    """Hacker News API 상위 스토리"""
    items = []
    cfg = sources_cfg.get('hacker_news', {})
    api_url = cfg.get('url', 'https://hacker-news.firebaseio.com/v0/topstories.json')
    top_n = cfg.get('top_n', 30)
    try:
        resp = requests.get(api_url, timeout=10)
        story_ids = resp.json()[:top_n]
        for sid in story_ids:
            story_resp = requests.get(
                f'https://hacker-news.firebaseio.com/v0/item/{sid}.json', timeout=5
            )
            story = story_resp.json()
            if not story or story.get('type') != 'story':
                continue
            pub_ts = story.get('time')
            pub_at = datetime.fromtimestamp(pub_ts, tz=timezone.utc).isoformat() if pub_ts else None
            items.append({
                'topic': story.get('title', ''),
                'description': story.get('url', ''),
                'source': 'hacker_news',
                'source_url': story.get('url', f'https://news.ycombinator.com/item?id={sid}'),
                'published_at': pub_at,
                'search_demand_score': 8,
                'topic_type': 'trending',
            })
    except Exception as e:
        logger.warning(f"Hacker News 수집 실패: {e}")
    return items


def collect_product_hunt(sources_cfg: dict) -> list[dict]:
    """Product Hunt RSS"""
    items = []
    cfg = sources_cfg.get('product_hunt', {})
    rss_url = cfg.get('rss_url', 'https://www.producthunt.com/feed')
    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:15]:
            pub_at = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                pub_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
            items.append({
                'topic': entry.get('title', ''),
                'description': entry.get('summary', ''),
                'source': 'product_hunt',
                'source_url': entry.get('link', ''),
                'published_at': pub_at,
                'search_demand_score': 10,
                'topic_type': 'trending',
            })
    except Exception as e:
        logger.warning(f"Product Hunt 수집 실패: {e}")
    return items


def collect_rss_feeds(sources_cfg: dict) -> list[dict]:
    """설정된 RSS 피드 수집"""
    items = []
    feeds = sources_cfg.get('rss_feeds', [])
    for feed_cfg in feeds:
        url = feed_cfg.get('url', '')
        trust = feed_cfg.get('trust_level', 'medium')
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                pub_at = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
                items.append({
                    'topic': entry.get('title', ''),
                    'description': entry.get('summary', '') or entry.get('description', ''),
                    'source': 'rss',
                    'source_name': feed_cfg.get('name', ''),
                    'source_url': entry.get('link', ''),
                    'published_at': pub_at,
                    'search_demand_score': 8,
                    'topic_type': 'trending',
                    '_trust_override': trust,
                })
        except Exception as e:
            logger.warning(f"RSS 수집 실패 ({url}): {e}")
    return items


def extract_coupang_keywords(topic: str, description: str) -> list[str]:
    """글감에서 쿠팡 검색 키워드 추출"""
    product_keywords = [
        '마이크', '웹캠', '키보드', '마우스', '모니터', '노트북', '이어폰',
        '헤드셋', '외장하드', 'USB허브', '책상', '의자', '서적', '책', '스피커',
    ]
    text = topic + ' ' + description
    found = [kw for kw in product_keywords if kw in text]
    if not found:
        # IT 기기 류 글이면 기본 키워드
        if any(kw in text for kw in ['도구', '앱', '툴', '소프트웨어', '서비스']):
            found = ['키보드', '마우스']
    return found


def save_discarded(item: dict, reason: str):
    """폐기된 글감 로그 저장"""
    discard_dir = DATA_DIR / 'discarded'
    discard_dir.mkdir(exist_ok=True)
    today = datetime.now().strftime('%Y%m%d')
    log_file = discard_dir / f'{today}_discarded.jsonl'
    record = {**item, 'discard_reason': reason, 'discarded_at': datetime.now().isoformat()}
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')


def save_topic(item: dict):
    """합격한 글감을 data/topics/에 저장"""
    topics_dir = DATA_DIR / 'topics'
    topics_dir.mkdir(exist_ok=True)
    topic_id = hashlib.md5(item['topic'].encode()).hexdigest()[:8]
    filename = f"{datetime.now().strftime('%Y%m%d')}_{topic_id}.json"
    with open(topics_dir / filename, 'w', encoding='utf-8') as f:
        json.dump(item, f, ensure_ascii=False, indent=2)


def run():
    logger.info("=== 수집봇 시작 ===")
    rules = load_config('quality_rules.json')
    sources_cfg = load_config('sources.json')
    published_titles = load_published_titles()
    min_score = rules.get('min_score', 70)

    # 수집
    all_items = []
    all_items += collect_google_trends()
    all_items += collect_github_trending(sources_cfg)
    all_items += collect_product_hunt(sources_cfg)
    all_items += collect_hacker_news(sources_cfg)
    all_items += collect_rss_feeds(sources_cfg)

    logger.info(f"수집 완료: {len(all_items)}개")

    passed = []
    discarded_count = 0

    for item in all_items:
        if not item.get('topic'):
            continue

        # 신뢰도 오버라이드 (RSS 피드별 설정)
        trust_override = item.pop('_trust_override', None)
        if trust_override:
            trust_levels = rules['scoring']['source_trust']['levels']
            item['source_trust_level'] = trust_override
            item['_trust_score'] = trust_levels.get(trust_override, trust_levels['medium'])

        # 품질 점수 계산
        score = calculate_quality_score(item, rules)
        item['quality_score'] = score

        # 폐기 규칙 검사
        discard_reason = apply_discard_rules(item, rules, published_titles)
        if discard_reason:
            save_discarded(item, discard_reason)
            discarded_count += 1
            logger.debug(f"폐기: [{score}점] {item['topic']} — {discard_reason}")
            continue

        if score < min_score:
            save_discarded(item, f'품질 점수 미달 ({score}점 < {min_score}점)')
            discarded_count += 1
            logger.debug(f"폐기: [{score}점] {item['topic']}")
            continue

        # 코너 배정
        topic_type = item.get('topic_type', 'trending')
        corner = assign_corner(item, topic_type)
        item['corner'] = corner

        # 쿠팡 키워드 추출
        item['coupang_keywords'] = extract_coupang_keywords(
            item.get('topic', ''), item.get('description', '')
        )

        # 트렌딩 경과 시간 표시
        pub_at_str = item.get('published_at')
        if pub_at_str:
            try:
                pub_at = datetime.fromisoformat(pub_at_str)
                if pub_at.tzinfo is None:
                    pub_at = pub_at.replace(tzinfo=timezone.utc)
                hours_ago = int((datetime.now(timezone.utc) - pub_at).total_seconds() / 3600)
                item['trending_since'] = f'{hours_ago}시간 전' if hours_ago < 24 else f'{hours_ago // 24}일 전'
            except Exception:
                item['trending_since'] = '알 수 없음'

        # sources 필드 정리
        item['sources'] = [{'url': item.get('source_url', ''), 'title': item.get('topic', ''),
                             'date': item.get('published_at', '')}]
        item['related_keywords'] = item.get('topic', '').split()[:5]

        passed.append(item)

    # 에버그린/트렌드/개성 비율 맞추기
    total_target = len(passed)
    evergreen = [i for i in passed if i.get('is_evergreen')]
    trending = [i for i in passed if not i.get('is_evergreen') and i.get('topic_type') == 'trending']
    personality = [i for i in passed if i.get('topic_type') == 'personality']

    logger.info(
        f"합격: {len(passed)}개 (에버그린 {len(evergreen)}, 트렌드 {len(trending)}, "
        f"개성 {len(personality)}) / 폐기: {discarded_count}개"
    )

    # 글감 저장
    for item in passed:
        save_topic(item)
        logger.info(f"[{item['quality_score']}점][{item['corner']}] {item['topic']}")

    logger.info("=== 수집봇 완료 ===")
    return passed


if __name__ == '__main__':
    run()
