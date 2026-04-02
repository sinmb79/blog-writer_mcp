"""
카드 변환봇 (converters/card_converter.py)
역할: 원본 마크다운 → 인스타그램 카드 이미지 (LAYER 2)
- 크기: 1080×1080 (정사각형)
- 배경: 흰색 + 골드 액센트 (#c8a84e)
- 폰트: Noto Sans KR (없으면 기본 폰트)
- 구성: 로고 + 코너 배지 + 제목 + 핵심 3줄 + URL
출력: data/outputs/{date}_{slug}_card.png
"""
import logging
import textwrap
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)
OUTPUT_DIR = BASE_DIR / 'data' / 'outputs'
OUTPUT_DIR.mkdir(exist_ok=True)
ASSETS_DIR = BASE_DIR / 'assets'
FONTS_DIR = ASSETS_DIR / 'fonts'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'converter.log', encoding='utf-8'),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

# 디자인 상수
CARD_SIZE = (1080, 1080)
COLOR_WHITE = (255, 255, 255)
COLOR_GOLD = (200, 168, 78)       # #c8a84e
COLOR_DARK = (30, 30, 30)
COLOR_GRAY = (120, 120, 120)
COLOR_GOLD_LIGHT = (255, 248, 220)

CORNER_COLORS = {
    '쉬운세상': (52, 152, 219),   # 파랑
    '숨은보물': (46, 204, 113),   # 초록
    '바이브리포트': (155, 89, 182),  # 보라
    '팩트체크': (231, 76, 60),    # 빨강
    '한컷': (241, 196, 15),       # 노랑
}

BLOG_URL = 'the4thpath.com'
BRAND_NAME = 'The 4th Path'
SUB_BRAND = 'by 22B Labs'


def _load_font(size: int):
    """Noto Sans KR 폰트 로드 (없으면 기본 폰트)"""
    try:
        from PIL import ImageFont
        for fname in ['NotoSansKR-Bold.ttf', 'NotoSansKR-Regular.ttf', 'NotoSansKR-Medium.ttf']:
            font_path = FONTS_DIR / fname
            if font_path.exists():
                return ImageFont.truetype(str(font_path), size)
        # Windows 기본 한글 폰트 시도
        for path in [
            'C:/Windows/Fonts/malgun.ttf',
            'C:/Windows/Fonts/malgunbd.ttf',
            'C:/Windows/Fonts/NanumGothic.ttf',
        ]:
            if Path(path).exists():
                return ImageFont.truetype(path, size)
    except Exception:
        pass
    try:
        from PIL import ImageFont
        return ImageFont.load_default()
    except Exception:
        return None


def _draw_rounded_rect(draw, xy, radius: int, fill):
    """PIL로 둥근 사각형 그리기"""
    from PIL import ImageDraw
    x1, y1, x2, y2 = xy
    draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
    draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
    draw.ellipse([x1, y1, x1 + radius * 2, y1 + radius * 2], fill=fill)
    draw.ellipse([x2 - radius * 2, y1, x2, y1 + radius * 2], fill=fill)
    draw.ellipse([x1, y2 - radius * 2, x1 + radius * 2, y2], fill=fill)
    draw.ellipse([x2 - radius * 2, y2 - radius * 2, x2, y2], fill=fill)


def convert(article: dict, save_file: bool = True) -> str:
    """
    article dict → 카드 이미지 PNG.
    Returns: 저장 경로 문자열 (save_file=False면 빈 문자열)
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        logger.error("Pillow가 설치되지 않음. pip install Pillow")
        return ''

    title = article.get('title', '')
    corner = article.get('corner', '쉬운세상')
    key_points = article.get('key_points', [])

    logger.info(f"카드 변환 시작: {title}")

    # 캔버스
    img = Image.new('RGB', CARD_SIZE, COLOR_WHITE)
    draw = ImageDraw.Draw(img)

    # 골드 상단 바 (80px)
    draw.rectangle([0, 0, 1080, 80], fill=COLOR_GOLD)

    # 브랜드명 (좌상단)
    font_brand = _load_font(36)
    font_sub = _load_font(22)
    font_corner = _load_font(26)
    font_title = _load_font(52)
    font_point = _load_font(38)
    font_url = _load_font(28)

    if font_brand:
        draw.text((40, 22), BRAND_NAME, font=font_brand, fill=COLOR_WHITE)
    if font_sub:
        draw.text((460, 28), SUB_BRAND, font=font_sub, fill=(240, 235, 210))

    # 코너 배지
    badge_color = CORNER_COLORS.get(corner, COLOR_GOLD)
    _draw_rounded_rect(draw, [40, 110, 250, 160], 20, badge_color)
    if font_corner:
        draw.text((60, 122), corner, font=font_corner, fill=COLOR_WHITE)

    # 제목 (멀티라인, 최대 3줄)
    title_lines = textwrap.wrap(title, width=18)[:3]
    y_title = 200
    for line in title_lines:
        if font_title:
            draw.text((40, y_title), line, font=font_title, fill=COLOR_DARK)
        y_title += 65

    # 구분선
    draw.rectangle([40, y_title + 10, 1040, y_title + 14], fill=COLOR_GOLD)

    # 핵심 포인트
    y_points = y_title + 40
    for i, point in enumerate(key_points[:3]):
        # 불릿 원
        draw.ellipse([40, y_points + 8, 64, y_points + 32], fill=COLOR_GOLD)
        if font_point:
            point_short = textwrap.shorten(point, width=22, placeholder='...')
            draw.text((76, y_points), point_short, font=font_point, fill=COLOR_DARK)
        y_points += 60

    # 하단 바 (URL + 브랜딩)
    draw.rectangle([0, 980, 1080, 1080], fill=COLOR_GOLD)
    if font_url:
        draw.text((40, 1008), BLOG_URL, font=font_url, fill=COLOR_WHITE)

    # 저장
    output_path = ''
    if save_file:
        slug = article.get('slug', 'article')
        date_str = datetime.now().strftime('%Y%m%d')
        filename = f"{date_str}_{slug}_card.png"
        output_path = str(OUTPUT_DIR / filename)
        img.save(output_path, 'PNG')
        logger.info(f"카드 저장: {output_path}")

    logger.info("카드 변환 완료")
    return output_path


if __name__ == '__main__':
    sample = {
        'title': 'ChatGPT 처음 쓰는 사람을 위한 완전 가이드',
        'slug': 'chatgpt-guide',
        'corner': '쉬운세상',
        'key_points': ['무료로 바로 시작 가능', 'GPT-4는 유료지만 3.5도 충분', '프롬프트가 결과를 결정한다'],
    }
    path = convert(sample)
    print(f"저장: {path}")
