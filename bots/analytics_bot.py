"""
분석봇 (analytics_bot.py)
역할: 블로그 성과 데이터 수집 및 리포트 생성
5대 핵심 지표:
1. 색인률 (Search Console)
2. 검색 CTR (Search Console)
3. 발행 후 14일 성과
4. 어필리에이트 클릭률 (수동 입력)
5. 체류시간 (Blogger 통계)
"""
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

load_dotenv(dotenv_path=Path(__file__).parent.parent / '.env')

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / 'data'
LOG_DIR = BASE_DIR / 'logs'
TOKEN_PATH = BASE_DIR / 'token.json'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'analytics.log', encoding='utf-8'),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
BLOG_MAIN_ID = os.getenv('BLOG_MAIN_ID', '')

SCOPES = [
    'https://www.googleapis.com/auth/blogger.readonly',
    'https://www.googleapis.com/auth/webmasters.readonly',
]


def get_google_credentials() -> Credentials:
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_PATH, 'w') as f:
                f.write(creds.to_json())
    return creds


def load_published_records() -> list[dict]:
    """발행 이력 전체 로드"""
    records = []
    published_dir = DATA_DIR / 'published'
    for f in published_dir.glob('*.json'):
        try:
            records.append(json.loads(f.read_text(encoding='utf-8')))
        except Exception:
            pass
    return sorted(records, key=lambda x: x.get('published_at', ''), reverse=True)


def send_telegram(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram 설정 없음")
        print(text)
        return
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    try:
        requests.post(url, json={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': text,
            'parse_mode': 'HTML',
        }, timeout=10)
    except Exception as e:
        logger.error(f"Telegram 전송 실패: {e}")


# ─── Search Console 데이터 ────────────────────────────

def get_search_console_data(site_url: str, start_date: str, end_date: str,
                             creds: Credentials) -> dict:
    """Search Console API로 검색 성과 조회"""
    try:
        service = build('searchconsole', 'v1', credentials=creds)
        request_body = {
            'startDate': start_date,
            'endDate': end_date,
            'dimensions': ['page'],
            'rowLimit': 1000,
        }
        resp = service.searchanalytics().query(
            siteUrl=site_url, body=request_body
        ).execute()
        return resp
    except Exception as e:
        logger.warning(f"Search Console API 오류: {e}")
        return {}


def calc_index_rate(published_records: list[dict], sc_data: dict) -> float:
    """색인률 계산: 발행 글 중 Search Console에 데이터가 있는 비율"""
    if not published_records:
        return 0.0
    sc_urls = set()
    for row in sc_data.get('rows', []):
        sc_urls.add(row.get('keys', [''])[0])

    indexed = sum(1 for r in published_records if r.get('url', '') in sc_urls)
    return round(indexed / len(published_records) * 100, 1)


def calc_average_ctr(sc_data: dict) -> float:
    """평균 CTR 계산"""
    rows = sc_data.get('rows', [])
    if not rows:
        return 0.0
    total_clicks = sum(r.get('clicks', 0) for r in rows)
    total_impressions = sum(r.get('impressions', 0) for r in rows)
    if total_impressions == 0:
        return 0.0
    return round(total_clicks / total_impressions * 100, 2)


def get_14day_performance(published_records: list[dict], sc_data: dict) -> list[dict]:
    """발행 후 14일 경과한 글들의 성과"""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=14)
    sc_rows_by_url = {}
    for row in sc_data.get('rows', []):
        url = row.get('keys', [''])[0]
        sc_rows_by_url[url] = row

    results = []
    for record in published_records:
        pub_str = record.get('published_at', '')
        try:
            pub_dt = datetime.fromisoformat(pub_str)
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if pub_dt > cutoff:
            continue  # 14일 미경과

        url = record.get('url', '')
        sc_row = sc_rows_by_url.get(url, {})
        clicks = sc_row.get('clicks', 0)
        impressions = sc_row.get('impressions', 0)
        results.append({
            'title': record.get('title', ''),
            'corner': record.get('corner', ''),
            'published_at': pub_str,
            'clicks_14d': clicks,
            'impressions_14d': impressions,
            'url': url,
        })
    return results


# ─── 리포트 생성 ──────────────────────────────────────

def format_daily_report(
    today_published: list[dict],
    index_rate: float,
    avg_ctr: float,
    total_published: int,
) -> str:
    today_str = datetime.now().strftime('%Y-%m-%d')
    today_count = len(today_published)
    today_titles = '\n'.join(
        f"  • [{r.get('corner', '')}] {r.get('title', '')}" for r in today_published
    )
    return (
        f"📊 <b>일일 리포트 — {today_str}</b>\n\n"
        f"📝 오늘 발행: {today_count}개\n"
        f"{today_titles}\n\n"
        f"📈 누적 발행: {total_published}개\n"
        f"🔍 색인률: {index_rate}%\n"
        f"🖱 평균 CTR: {avg_ctr}%\n\n"
        f"Phase 1 목표: 색인률 80%+, CTR 3%+"
    )


def format_weekly_report(
    index_rate: float,
    avg_ctr: float,
    by_corner: dict,
    low_performers: list[dict],
) -> str:
    today_str = datetime.now().strftime('%Y-%m-%d')
    corner_lines = '\n'.join(
        f"  • {corner}: {count}개" for corner, count in by_corner.items()
    )
    low_lines = '\n'.join(
        f"  ⚠ {r['title']} (클릭 {r['clicks_14d']}회)" for r in low_performers[:5]
    ) or '  없음'

    return (
        f"📊 <b>주간 리포트 — {today_str}</b>\n\n"
        f"🔍 색인률: {index_rate}%\n"
        f"🖱 평균 CTR: {avg_ctr}%\n\n"
        f"📁 코너별 발행 수:\n{corner_lines}\n\n"
        f"⚠ 14일 성과 부진 글 (클릭 0):\n{low_lines}\n\n"
        f"💡 피드백 루프 적용 완료 → 다음 주 글감 조정"
    )


def save_analytics(data: dict, filename: str):
    analytics_dir = DATA_DIR / 'analytics'
    analytics_dir.mkdir(exist_ok=True)
    with open(analytics_dir / filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def generate_feedback_json(index_rate: float, avg_ctr: float,
                            low_performers: list[dict], by_corner: dict) -> dict:
    """수집봇에 피드백할 데이터 생성"""
    feedback = {
        'generated_at': datetime.now().isoformat(),
        'metrics': {
            'index_rate': index_rate,
            'avg_ctr': avg_ctr,
        },
        'adjustments': [],
    }

    if index_rate < 50:
        feedback['adjustments'].append({
            'type': 'warning',
            'message': '색인률 50% 미만 — 글 구조/Schema 점검 필요',
        })
    if avg_ctr < 1:
        feedback['adjustments'].append({
            'type': 'title_meta',
            'message': 'CTR 1% 미만 — 제목/메타 설명 스타일 변경 권고',
        })

    # 성과 좋은 코너 확대
    max_corner = max(by_corner, key=by_corner.get) if by_corner else None
    if max_corner:
        feedback['adjustments'].append({
            'type': 'corner_boost',
            'corner': max_corner,
            'message': f'{max_corner} 코너 성과 우수 — 비율 확대 권고',
        })

    # 14일 성과 0인 글감 유형 축소
    if low_performers:
        bad_corners = list({r['corner'] for r in low_performers if r['clicks_14d'] == 0})
        for corner in bad_corners:
            feedback['adjustments'].append({
                'type': 'corner_reduce',
                'corner': corner,
                'message': f'{corner} 코너 14일 성과 부진 — 주제 유형 축소 권고',
            })

    return feedback


# ─── 메인 실행 ───────────────────────────────────────

def daily_report():
    """일일 리포트 생성 및 Telegram 전송"""
    logger.info("=== 분석봇 일일 리포트 시작 ===")
    published_records = load_published_records()

    # 오늘 발행 글
    today_str = datetime.now().strftime('%Y-%m-%d')
    today_published = [
        r for r in published_records
        if r.get('published_at', '').startswith(today_str)
    ]

    # Search Console 데이터 (최근 7일)
    sc_data = {}
    try:
        creds = get_google_credentials()
        if creds and creds.valid:
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            # site_url은 블로그 URL (예: https://techinsider-kr.blogspot.com/)
            # 설정에서 읽어오거나 환경변수로 관리
            site_url = os.getenv('BLOG_SITE_URL', '')
            if site_url:
                sc_data = get_search_console_data(site_url, start_date, end_date, creds)
    except Exception as e:
        logger.warning(f"Search Console 조회 실패: {e}")

    index_rate = calc_index_rate(published_records, sc_data)
    avg_ctr = calc_average_ctr(sc_data)

    report_text = format_daily_report(
        today_published, index_rate, avg_ctr, len(published_records)
    )
    send_telegram(report_text)

    # 저장
    save_analytics({
        'date': today_str,
        'today_published': len(today_published),
        'total_published': len(published_records),
        'index_rate': index_rate,
        'avg_ctr': avg_ctr,
    }, f'{today_str}_daily.json')

    logger.info("=== 분석봇 일일 리포트 완료 ===")


def weekly_report():
    """주간 리포트 생성 및 Telegram 전송"""
    logger.info("=== 분석봇 주간 리포트 시작 ===")
    published_records = load_published_records()

    # Search Console 데이터 (최근 28일)
    sc_data = {}
    try:
        creds = get_google_credentials()
        if creds and creds.valid:
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=28)).strftime('%Y-%m-%d')
            site_url = os.getenv('BLOG_SITE_URL', '')
            if site_url:
                sc_data = get_search_console_data(site_url, start_date, end_date, creds)
    except Exception as e:
        logger.warning(f"Search Console 조회 실패: {e}")

    index_rate = calc_index_rate(published_records, sc_data)
    avg_ctr = calc_average_ctr(sc_data)
    perf_14d = get_14day_performance(published_records, sc_data)

    # 코너별 발행 수
    by_corner: dict[str, int] = {}
    for r in published_records:
        corner = r.get('corner', '기타')
        by_corner[corner] = by_corner.get(corner, 0) + 1

    # 14일 성과 부진 글
    low_performers = [r for r in perf_14d if r['clicks_14d'] == 0]

    report_text = format_weekly_report(index_rate, avg_ctr, by_corner, low_performers)
    send_telegram(report_text)

    # 피드백 JSON 생성
    feedback = generate_feedback_json(index_rate, avg_ctr, low_performers, by_corner)
    save_analytics(feedback, f"{datetime.now().strftime('%Y%m%d')}_feedback.json")

    logger.info("=== 분석봇 주간 리포트 완료 ===")
    return feedback


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'weekly':
        weekly_report()
    else:
        daily_report()
