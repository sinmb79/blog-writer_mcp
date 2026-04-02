"""
novel_blog_converter.py
소설 연재 파이프라인 — 에피소드 → Blogger-ready HTML 변환 모듈
역할: 에피소드 dict + 소설 설정 → 장르별 테마 HTML 생성
출력: data/novels/{novel_id}/episodes/ep{N:03d}_blog.html
"""
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / '.env')

BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR / 'bots'))

logger = logging.getLogger(__name__)

BLOG_BASE_URL = 'https://the4thpath.com'

# ─── 장르별 컬러 테마 ─────────────────────────────────────────────────────────

GENRE_THEMES = {
    'sci-fi': {
        'bg': '#0a0f1e',
        'accent': '#00bcd4',
        'accent_dim': '#007c8c',
        'card_bg': '#0e1628',
        'text': '#cfe8ef',
        'meta': '#6fa8bc',
        'nav_bg': '#0c1220',
    },
    'thriller': {
        'bg': '#0a0a0d',
        'accent': '#bf3a3a',
        'accent_dim': '#8a2222',
        'card_bg': '#141418',
        'text': '#e8e0e0',
        'meta': '#a08080',
        'nav_bg': '#111115',
    },
    'fantasy': {
        'bg': '#0f0a1e',
        'accent': '#c8a84e',
        'accent_dim': '#8a7030',
        'card_bg': '#180f2e',
        'text': '#e8e0f0',
        'meta': '#9a8ab0',
        'nav_bg': '#130c22',
    },
    'romance': {
        'bg': '#ffffff',
        'accent': '#d85a30',
        'accent_dim': '#a04020',
        'card_bg': '#fff5f0',
        'text': '#2a1a14',
        'meta': '#8a5a4a',
        'nav_bg': '#fff0ea',
    },
    'default': {
        'bg': '#0a0a0d',
        'accent': '#c8a84e',
        'accent_dim': '#8a7030',
        'card_bg': '#141418',
        'text': '#e8e0d0',
        'meta': '#a09070',
        'nav_bg': '#111115',
    },
}


def _get_theme(genre: str) -> dict:
    """장르 문자열에서 테마 결정 (부분 매칭 포함)"""
    genre_lower = genre.lower()
    for key in GENRE_THEMES:
        if key in genre_lower:
            return GENRE_THEMES[key]
    return GENRE_THEMES['default']


def _build_json_ld(episode: dict, novel_config: dict, post_url: str = '') -> str:
    """Schema.org Article JSON-LD 생성"""
    schema = {
        '@context': 'https://schema.org',
        '@type': 'Article',
        'headline': f"{novel_config.get('title_ko', '')} {episode.get('episode_num', 0)}화 — {episode.get('title', '')}",
        'description': episode.get('hook', ''),
        'datePublished': datetime.now(timezone.utc).isoformat(),
        'dateModified': datetime.now(timezone.utc).isoformat(),
        'author': {
            '@type': 'Person',
            'name': 'The 4th Path'
        },
        'publisher': {
            '@type': 'Organization',
            'name': 'The 4th Path',
            'logo': {
                '@type': 'ImageObject',
                'url': f'{BLOG_BASE_URL}/logo.png'
            }
        },
        'mainEntityOfPage': {
            '@type': 'WebPage',
            '@id': post_url or BLOG_BASE_URL
        },
        'genre': novel_config.get('genre', ''),
        'isPartOf': {
            '@type': 'CreativeWorkSeries',
            'name': novel_config.get('title_ko', ''),
            'position': episode.get('episode_num', 0)
        }
    }
    return (
        '<script type="application/ld+json">\n'
        + json.dumps(schema, ensure_ascii=False, indent=2)
        + '\n</script>'
    )


def _body_to_html(body_text: str) -> str:
    """소설 본문 텍스트 → HTML 단락 변환 (빈 줄 기준 분리)"""
    paragraphs = []
    for para in body_text.split('\n\n'):
        para = para.strip()
        if not para:
            continue
        # 대화문 들여쓰기 처리
        lines = para.split('\n')
        html_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # HTML 특수문자 이스케이프
            line = (line.replace('&', '&amp;')
                        .replace('<', '&lt;')
                        .replace('>', '&gt;'))
            # 대화문 (따옴표 시작) 스타일 적용
            if line.startswith('"') or line.startswith('"') or line.startswith('"'):
                html_lines.append(
                    f'<span style="color:inherit;opacity:0.9">{line}</span>'
                )
            else:
                html_lines.append(line)
        paragraphs.append('<br>\n'.join(html_lines))

    return '\n'.join(
        f'<p style="margin:0 0 1.6em 0;line-height:1.9;letter-spacing:0.01em">{p}</p>'
        for p in paragraphs if p
    )


def convert(
    episode: dict,
    novel_config: dict,
    prev_url: str = '',
    next_url: str = '',
    save_file: bool = True
) -> str:
    """
    에피소드 + 소설 설정 → Blogger-ready HTML.
    data/novels/{novel_id}/episodes/ep{N:03d}_blog.html 저장.
    반환: HTML 문자열
    """
    novel_id = novel_config.get('novel_id', episode.get('novel_id', 'unknown'))
    ep_num = episode.get('episode_num', 0)
    title = episode.get('title', f'에피소드 {ep_num}')
    body_text = episode.get('body', '')
    hook = episode.get('hook', '')
    genre = novel_config.get('genre', '')
    title_ko = novel_config.get('title_ko', '')

    logger.info(f"[{novel_id}] 에피소드 {ep_num} 블로그 변환 시작")

    theme = _get_theme(genre)
    bg = theme['bg']
    accent = theme['accent']
    accent_dim = theme['accent_dim']
    card_bg = theme['card_bg']
    text_color = theme['text']
    meta_color = theme['meta']
    nav_bg = theme['nav_bg']

    # 다음 에피소드 예정일 (publish_schedule 파싱 — 간단 처리)
    next_date_str = '다음 회 예고'
    try:
        schedule = novel_config.get('publish_schedule', '')
        # "매주 월/목 09:00" 형식에서 요일 추출
        if schedule:
            next_date_str = schedule.replace('매주 ', '').replace('09:00', '').strip()
    except Exception:
        pass

    # 본문 HTML
    body_html = _body_to_html(body_text)

    # JSON-LD
    post_url = ''
    json_ld = _build_json_ld(episode, novel_config, post_url)

    # 이전/다음 네비게이션
    prev_link = (
        f'<a href="{prev_url}" style="color:{accent};text-decoration:none;font-size:14px">&#8592; {ep_num - 1}화</a>'
        if prev_url and ep_num > 1
        else f'<span style="color:{meta_color};font-size:14px">첫 번째 에피소드</span>'
    )
    next_link = (
        f'<a href="{next_url}" style="color:{accent};text-decoration:none;font-size:14px">{ep_num + 1}화 &#8594;</a>'
        if next_url
        else f'<span style="color:{meta_color};font-size:14px">다음 회 업데이트 예정</span>'
    )

    # 전체 HTML 조립
    html = f"""{json_ld}
<style>
.post-title {{ display:none!important }}
</style>

<div style="max-width:680px;margin:0 auto;padding:24px 16px;background:{bg};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Malgun Gothic','Apple SD Gothic Neo',sans-serif;color:{text_color}">

  <!-- 에피소드 배지 -->
  <div style="margin-bottom:20px">
    <span style="display:inline-block;background:{accent};color:#fff;font-size:12px;font-weight:700;letter-spacing:0.08em;padding:5px 14px;border-radius:20px;text-transform:uppercase">
      연재소설 · 에피소드 {ep_num}
    </span>
  </div>

  <!-- 소설 제목 -->
  <p style="margin:0 0 6px 0;font-size:13px;color:{meta_color};letter-spacing:0.05em;font-weight:600">
    {title_ko}
  </p>

  <!-- 에피소드 제목 -->
  <h1 style="margin:0 0 20px 0;font-size:28px;font-weight:800;line-height:1.3;color:#fff;letter-spacing:-0.01em">
    {title}
  </h1>

  <!-- 메타 정보 -->
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:32px;padding-bottom:20px;border-bottom:1px solid {accent_dim}40">
    <span style="font-size:13px;color:{meta_color}">{genre}</span>
    <span style="color:{accent_dim}">·</span>
    <span style="font-size:13px;color:{meta_color}">{novel_config.get('episode_length','')}</span>
    <span style="color:{accent_dim}">·</span>
    <span style="font-size:13px;color:{meta_color}">{datetime.now().strftime('%Y.%m.%d')}</span>
  </div>

  <!-- 에피소드 이전/다음 네비게이션 (상단) -->
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:32px;padding:14px 18px;background:{nav_bg};border-radius:10px;border:1px solid {accent_dim}30">
    {prev_link}
    <span style="font-size:12px;color:{meta_color};font-weight:600">{ep_num}화</span>
    {next_link}
  </div>

  <!-- 본문 -->
  <div style="font-size:17px;line-height:1.9;color:{text_color}">
    {body_html}
  </div>

  <!-- 구분선 -->
  <div style="margin:40px 0 32px 0;height:2px;background:linear-gradient(to right,{accent},{accent}00)"></div>

  <!-- 클로징 박스: 다음 에피소드 예고 -->
  <div style="background:{card_bg};border-left:4px solid {accent};border-radius:0 12px 12px 0;padding:20px 22px;margin-bottom:32px">
    <p style="margin:0 0 8px 0;font-size:12px;font-weight:700;color:{accent};letter-spacing:0.08em;text-transform:uppercase">
      다음 에피소드 예고 · {next_date_str}
    </p>
    <p style="margin:0;font-size:15px;line-height:1.7;color:{text_color}">
      {hook if hook else '다음 회를 기대해 주세요.'}
    </p>
  </div>

  <!-- AdSense 슬롯 -->
  <!-- AD_SLOT_NOVEL -->

  <!-- 에피소드 이전/다음 네비게이션 (하단) -->
  <div style="display:flex;justify-content:space-between;align-items:center;margin-top:32px;padding:14px 18px;background:{nav_bg};border-radius:10px;border:1px solid {accent_dim}30">
    {prev_link}
    <a href="#" style="color:{meta_color};text-decoration:none;font-size:13px">&#8593; 목록</a>
    {next_link}
  </div>

  <!-- 소설 정보 푸터 -->
  <div style="margin-top:32px;padding:20px;background:{card_bg};border-radius:12px;border:1px solid {accent_dim}20">
    <p style="margin:0 0 8px 0;font-size:13px;font-weight:700;color:{accent}">
      {title_ko} 정보
    </p>
    <p style="margin:0 0 6px 0;font-size:13px;color:{meta_color}">
      장르: {genre} · 목표 {novel_config.get('episode_count_target', 20)}화 완결
    </p>
    <p style="margin:0;font-size:12px;color:{meta_color}">
      연재 일정: {novel_config.get('publish_schedule', '')} · The 4th Path
    </p>
  </div>

</div>"""

    if save_file:
        output_dir = BASE_DIR / 'data' / 'novels' / novel_id / 'episodes'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f'ep{ep_num:03d}_blog.html'
        try:
            output_path.write_text(html, encoding='utf-8')
            logger.info(f"블로그 HTML 저장: {output_path}")
        except Exception as e:
            logger.error(f"블로그 HTML 저장 실패: {e}")

    logger.info(f"[{novel_id}] 에피소드 {ep_num} 블로그 변환 완료")
    return html


# ─── 직접 실행 테스트 ─────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys as _sys
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s [%(levelname)s] %(message)s')

    # 샘플 테스트
    sample_config = json.loads(
        (BASE_DIR / 'config' / 'novels' / 'shadow-protocol.json')
        .read_text(encoding='utf-8')
    )
    sample_episode = {
        'novel_id': 'shadow-protocol',
        'episode_num': 1,
        'title': '프로토콜',
        'body': '빗소리가 유리창을 두드렸다.\n\n서진은 모니터를 응시했다.',
        'hook': '아리아의 목소리가 처음으로 떨렸다.',
        'key_scenes': [
            '서진이 빗속에서 데이터를 분석하는 장면',
            '아리아가 이상 신호를 감지하는 장면',
            '감시 드론이 서진의 아파트 창문을 지나가는 장면',
        ],
        'summary': '서진은 오라클 시스템에서 숨겨진 프로토콜을 발견한다.',
        'generated_at': '2026-03-26T00:00:00+00:00',
    }
    html = convert(sample_episode, sample_config)
    print(f"HTML 생성 완료: {len(html)}자")
