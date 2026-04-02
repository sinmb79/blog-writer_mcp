"""
쇼츠 변환봇 (converters/shorts_converter.py)
역할: 원본 마크다운 → 뉴스앵커 포맷 쇼츠 MP4 (LAYER 2)
설계서: shorts-video-template-spec.txt

파이프라인:
  1. 슬라이드 구성 결정 (intro/headline/point×3/data?/outro)
  2. 각 섹션 TTS 생성 → 개별 WAV
  3. DALL-E 배경 이미지 생성 (선택)
  4. Pillow UI 오버레이 합성 → 슬라이드 PNG × N
  5. 슬라이드 → 개별 클립 MP4 (Ken Burns zoompan)
  6. xfade 전환으로 클립 결합
  7. BGM 믹스 (8%)
  8. SRT 자막 burn-in
  9. 최종 MP4 저장

출력: data/outputs/{date}_{slug}_shorts.mp4 (1080×1920, 30~60초)

사전 조건:
  pip install Pillow pydub google-cloud-texttospeech openai gTTS
  ffmpeg 설치 후 PATH 등록 또는 FFMPEG_PATH 환경변수
"""
import base64
import json
import logging
import os
import subprocess
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / '.env')

BASE_DIR = Path(__file__).parent.parent.parent
LOG_DIR = BASE_DIR / 'logs'
OUTPUT_DIR = BASE_DIR / 'data' / 'outputs'
ASSETS_DIR = BASE_DIR / 'assets'
FONTS_DIR = ASSETS_DIR / 'fonts'
TEMPLATE_PATH = BASE_DIR / 'templates' / 'shorts_template.json'
BGM_PATH = ASSETS_DIR / 'bgm.mp3'

LOG_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(LOG_DIR / 'converter.log', encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(handler)
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.INFO)

FFMPEG = os.getenv('FFMPEG_PATH', 'ffmpeg')
FFPROBE = os.getenv('FFPROBE_PATH', 'ffprobe')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
GOOGLE_TTS_API_KEY = os.getenv('GOOGLE_TTS_API_KEY', '')

# 컬러 상수
COLOR_DARK = (10, 10, 13)        # #0a0a0d
COLOR_DARK2 = (15, 10, 30)       # #0f0a1e
COLOR_GOLD = (200, 168, 78)      # #c8a84e
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (0, 0, 0)
COLOR_TICKER_BG = (0, 0, 0, 200)


# ─── 설정 로드 ────────────────────────────────────────

def _load_template() -> dict:
    if TEMPLATE_PATH.exists():
        return json.loads(TEMPLATE_PATH.read_text(encoding='utf-8'))
    return {}


# ─── 폰트 헬퍼 ───────────────────────────────────────

def _load_font(size: int, bold: bool = False):
    """NotoSansKR 로드, 없으면 Windows 맑은고딕, 없으면 기본 폰트"""
    try:
        from PIL import ImageFont
        candidates = (
            ['NotoSansKR-Bold.ttf', 'NotoSansKR-Medium.ttf'] if bold
            else ['NotoSansKR-Regular.ttf', 'NotoSansKR-Medium.ttf']
        )
        for fname in candidates:
            p = FONTS_DIR / fname
            if p.exists():
                return ImageFont.truetype(str(p), size)
        win_font = 'malgunbd.ttf' if bold else 'malgun.ttf'
        wp = Path(f'C:/Windows/Fonts/{win_font}')
        if wp.exists():
            return ImageFont.truetype(str(wp), size)
        return ImageFont.load_default()
    except Exception:
        return None


def _text_size(draw, text: str, font) -> tuple[int, int]:
    """PIL 버전 호환 텍스트 크기 측정"""
    try:
        bb = draw.textbbox((0, 0), text, font=font)
        return bb[2] - bb[0], bb[3] - bb[1]
    except AttributeError:
        return draw.textsize(text, font=font)


# ─── Pillow 헬퍼 ─────────────────────────────────────

def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _draw_rounded_rect(draw, xy, radius: int, fill):
    x1, y1, x2, y2 = xy
    r = radius
    draw.rectangle([x1 + r, y1, x2 - r, y2], fill=fill)
    draw.rectangle([x1, y1 + r, x2, y2 - r], fill=fill)
    for cx, cy in [(x1, y1), (x2 - 2*r, y1), (x1, y2 - 2*r), (x2 - 2*r, y2 - 2*r)]:
        draw.ellipse([cx, cy, cx + 2*r, cy + 2*r], fill=fill)


def _draw_gradient_overlay(img, top_alpha: int = 0, bottom_alpha: int = 200):
    """하단 다크 그라데이션 오버레이"""
    from PIL import Image
    W, H = img.size
    overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    import struct
    for y in range(H // 2, H):
        t = (y - H // 2) / (H // 2)
        alpha = int(top_alpha + (bottom_alpha - top_alpha) * t)
        for x in range(W):
            overlay.putpixel((x, y), (0, 0, 0, alpha))
    return Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')


def _wrap_text_lines(text: str, font, max_width: int, draw) -> list[str]:
    """폰트 기준 줄 바꿈"""
    words = text.split()
    lines = []
    current = ''
    for word in words:
        test = (current + ' ' + word).strip()
        w, _ = _text_size(draw, test, font)
        if w <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# ─── TTS ──────────────────────────────────────────────

def _tts_google_rest(text: str, output_path: str, voice: str, speed: float) -> bool:
    """Google Cloud TTS REST API (API Key 방식)"""
    if not GOOGLE_TTS_API_KEY:
        return False
    try:
        import requests as req
        url = f'https://texttospeech.googleapis.com/v1/text:synthesize?key={GOOGLE_TTS_API_KEY}'
        lang = 'ko-KR' if voice.startswith('ko') else 'en-US'
        payload = {
            'input': {'text': text},
            'voice': {'languageCode': lang, 'name': voice},
            'audioConfig': {
                'audioEncoding': 'LINEAR16',
                'speakingRate': speed,
                'pitch': 0,
            },
        }
        resp = req.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        audio_b64 = resp.json().get('audioContent', '')
        if audio_b64:
            Path(output_path).write_bytes(base64.b64decode(audio_b64))
            return True
    except Exception as e:
        logger.warning(f"Google Cloud TTS 실패: {e}")
    return False


def _tts_gtts(text: str, output_path: str) -> bool:
    """gTTS 무료 (mp3 → pydub으로 wav 변환)"""
    try:
        from gtts import gTTS
        mp3_path = output_path.replace('.wav', '_tmp.mp3')
        tts = gTTS(text=text, lang='ko', slow=False)
        tts.save(mp3_path)
        # mp3 → wav
        _run_ffmpeg(['-i', mp3_path, '-ar', '24000', output_path], quiet=True)
        Path(mp3_path).unlink(missing_ok=True)
        return Path(output_path).exists()
    except Exception as e:
        logger.warning(f"gTTS 실패: {e}")
    return False


def synthesize_section(text: str, output_path: str, voice: str, speed: float) -> bool:
    """섹션별 TTS 생성 (Google Cloud REST → gTTS fallback)"""
    if _tts_google_rest(text, output_path, voice, speed):
        return True
    return _tts_gtts(text, output_path)


def get_audio_duration(wav_path: str) -> float:
    """ffprobe로 오디오 파일 길이(초) 측정"""
    try:
        result = subprocess.run(
            [FFPROBE, '-v', 'quiet', '-print_format', 'json',
             '-show_format', wav_path],
            capture_output=True, text=True, timeout=10
        )
        data = json.loads(result.stdout)
        return float(data['format']['duration'])
    except Exception:
        # 폴백: 텍스트 길이 추정 (한국어 약 4자/초)
        return max(2.0, len(text) / 4.0) if 'text' in dir() else 5.0


# ─── DALL-E 배경 이미지 ────────────────────────────────

def generate_background_dalle(prompt: str, corner: str) -> Optional['Image']:
    """
    DALL-E 3로 배경 이미지 생성 (1024×1792 → 1080×1920 리사이즈).
    OPENAI_API_KEY 없으면 None 반환 → 단색 배경 사용.
    """
    if not OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI
        from PIL import Image
        import io, requests as req

        client = OpenAI(api_key=OPENAI_API_KEY)
        full_prompt = prompt + ' No text, no letters, no numbers, no watermarks.'
        response = client.images.generate(
            model='dall-e-3',
            prompt=full_prompt,
            size='1024x1792',
            quality='standard',
            n=1,
        )
        img_url = response.data[0].url
        img_bytes = req.get(img_url, timeout=30).content
        img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
        img = img.resize((1080, 1920), Image.LANCZOS)
        logger.info(f"DALL-E 배경 생성 완료: {corner}")
        return img
    except Exception as e:
        logger.warning(f"DALL-E 배경 생성 실패 (단색 사용): {e}")
        return None


def solid_background(color: tuple) -> 'Image':
    """단색 배경 이미지 생성"""
    from PIL import Image
    return Image.new('RGB', (1080, 1920), color)


# ─── 슬라이드 합성 ────────────────────────────────────

def compose_intro_slide(cfg: dict) -> str:
    """인트로 슬라이드: 다크 배경 + 로고 + 브랜드"""
    from PIL import Image, ImageDraw
    img = solid_background(COLOR_DARK)
    draw = ImageDraw.Draw(img)

    W, H = 1080, 1920

    # 골드 수평선 (상단 1/3)
    draw.rectangle([60, H//3 - 2, W - 60, H//3], fill=COLOR_GOLD)

    # 브랜드명
    font_brand = _load_font(cfg.get('font_title_size', 72), bold=True)
    font_sub = _load_font(cfg.get('font_body_size', 48))
    font_meta = _load_font(cfg.get('font_meta_size', 32))

    brand = cfg.get('brand_name', 'The 4th Path')
    sub = cfg.get('brand_sub', 'Independent Tech Media')
    by_text = cfg.get('brand_by', 'by 22B Labs')

    if font_brand:
        bw, bh = _text_size(draw, brand, font_brand)
        draw.text(((W - bw) // 2, H // 3 + 60), brand, font=font_brand, fill=COLOR_GOLD)
    if font_sub:
        sw, sh = _text_size(draw, sub, font_sub)
        draw.text(((W - sw) // 2, H // 3 + 60 + (bh if font_brand else 72) + 24),
                  sub, font=font_sub, fill=COLOR_WHITE)
    if font_meta:
        mw, mh = _text_size(draw, by_text, font_meta)
        draw.text(((W - mw) // 2, H * 2 // 3), by_text, font=font_meta, fill=COLOR_GOLD)

    path = str(_tmp_slide('intro'))
    img.save(path)
    return path


def compose_headline_slide(article: dict, cfg: dict, bg_img=None) -> str:
    """헤드라인 슬라이드: DALL-E 배경 + 코너 배지 + 제목 + 날짜"""
    from PIL import Image, ImageDraw

    corner = article.get('corner', '쉬운세상')
    corner_cfg = cfg.get('corners', {}).get(corner, {})
    corner_color = _hex_to_rgb(corner_cfg.get('color', '#c8a84e'))

    if bg_img is None:
        bg_img = solid_background((20, 20, 35))

    img = _draw_gradient_overlay(bg_img.copy())
    draw = ImageDraw.Draw(img)
    W, H = 1080, 1920

    font_badge = _load_font(36)
    font_title = _load_font(cfg.get('font_title_size', 72), bold=True)
    font_meta = _load_font(cfg.get('font_meta_size', 32))

    # 코너 배지
    _draw_rounded_rect(draw, [60, 120, 60 + len(corner) * 28 + 40, 190], 20, corner_color)
    if font_badge:
        draw.text((80, 133), corner, font=font_badge, fill=COLOR_WHITE)

    # 제목 (최대 3줄)
    title = article.get('title', '')
    if font_title:
        lines = _wrap_text_lines(title, font_title, W - 120, draw)[:3]
        y = H // 2 - (len(lines) * 90) // 2
        for line in lines:
            draw.text((60, y), line, font=font_title, fill=COLOR_WHITE)
            y += 90

    # 날짜 + 브랜드
    meta_text = f"{datetime.now().strftime('%Y.%m.%d')}  ·  22B Labs"
    if font_meta:
        draw.text((60, H - 160), meta_text, font=font_meta, fill=COLOR_GOLD)

    # 하단 골드 선
    draw.rectangle([0, H - 100, W, H - 96], fill=COLOR_GOLD)

    path = str(_tmp_slide('headline'))
    img.save(path)
    return path


def compose_point_slide(point: str, num: int, article: dict, cfg: dict,
                         bg_img=None) -> str:
    """포인트 슬라이드: 번호 배지 + 핵심 포인트 + 뉴스 티커"""
    from PIL import Image, ImageDraw

    corner = article.get('corner', '쉬운세상')
    corner_cfg = cfg.get('corners', {}).get(corner, {})
    corner_color = _hex_to_rgb(corner_cfg.get('color', '#c8a84e'))

    if bg_img is None:
        bg_img = solid_background((20, 15, 35))

    # 배경 어둡게
    from PIL import ImageEnhance
    img = ImageEnhance.Brightness(bg_img.copy()).enhance(0.4)
    draw = ImageDraw.Draw(img)
    W, H = 1080, 1920

    font_num = _load_font(80, bold=True)
    font_point = _load_font(cfg.get('font_body_size', 48))
    font_ticker = _load_font(cfg.get('font_ticker_size', 28))

    # 번호 원형 배지
    badges = ['①', '②', '③']
    badge_char = badges[num - 1] if num <= 3 else str(num)
    if font_num:
        draw.ellipse([60, 160, 200, 300], fill=corner_color)
        bw, bh = _text_size(draw, badge_char, font_num)
        draw.text((60 + (140 - bw) // 2, 160 + (140 - bh) // 2),
                  badge_char, font=font_num, fill=COLOR_WHITE)

    # 포인트 텍스트
    if font_point:
        lines = _wrap_text_lines(point, font_point, W - 120, draw)[:4]
        y = H // 2 - (len(lines) * 70) // 2
        for line in lines:
            draw.text((60, y), line, font=font_point, fill=COLOR_WHITE)
            y += 70

    # 뉴스 티커 바 (하단)
    ticker_text = cfg.get('ticker_text', 'The 4th Path · {corner} · {date}')
    ticker_text = ticker_text.format(
        corner=corner, date=datetime.now().strftime('%Y.%m.%d')
    )
    draw.rectangle([0, H - 100, W, H], fill=COLOR_BLACK)
    if font_ticker:
        draw.text((30, H - 78), ticker_text, font=font_ticker, fill=COLOR_GOLD)

    path = str(_tmp_slide(f'point{num}'))
    img.save(path)
    return path


def compose_data_slide(article: dict, cfg: dict) -> str:
    """데이터 카드 슬라이드: 다크 배경 + 수치 카드 2~3개"""
    from PIL import Image, ImageDraw

    img = solid_background(COLOR_DARK2)
    draw = ImageDraw.Draw(img)
    W, H = 1080, 1920

    font_num = _load_font(100, bold=True)
    font_label = _load_font(40)
    font_meta = _load_font(30)

    # KEY_POINTS에서 수치 추출 시도 (간단 파싱)
    key_points = article.get('key_points', [])
    import re
    data_items = []
    for kp in key_points:
        nums = re.findall(r'\d[\d,.%억만조]+|\d+[%배x]', kp)
        if nums:
            data_items.append({'value': nums[0], 'label': kp[:20]})

    # 수치가 없으면 포인트를 카드로 표시
    if not data_items:
        data_items = [{'value': f'0{i+1}', 'label': kp[:20]}
                      for i, kp in enumerate(key_points[:3])]

    # 카드 그리기 (최대 3개)
    card_w = 420
    card_h = 300
    items = data_items[:3]
    cols = min(len(items), 2)
    x_start = (W - cols * card_w - (cols - 1) * 30) // 2
    y_start = H // 2 - card_h // 2 - (len(items) > 2) * (card_h // 2 + 20)

    for i, item in enumerate(items):
        col = i % cols
        row = i // cols
        x = x_start + col * (card_w + 30)
        y = y_start + row * (card_h + 30)

        _draw_rounded_rect(draw, [x, y, x + card_w, y + card_h], 16,
                           (30, 25, 60))
        draw.rectangle([x, y, x + card_w, y + 6], fill=COLOR_GOLD)  # 상단 강조선

        if font_num:
            vw, vh = _text_size(draw, item['value'], font_num)
            draw.text((x + (card_w - vw) // 2, y + 60),
                      item['value'], font=font_num, fill=COLOR_GOLD)
        if font_label:
            lw, lh = _text_size(draw, item['label'], font_label)
            draw.text((x + (card_w - lw) // 2, y + 190),
                      item['label'], font=font_label, fill=COLOR_WHITE)

    # 출처 표시
    sources = article.get('sources', [])
    if sources and font_meta:
        src_title = sources[0].get('title', '')[:40]
        draw.text((60, H - 200), f'출처: {src_title}', font=font_meta,
                  fill=(150, 150, 150))

    path = str(_tmp_slide('data'))
    img.save(path)
    return path


def compose_outro_slide(cfg: dict) -> str:
    """아웃트로 슬라이드: 다크 배경 + CTA + URL"""
    from PIL import Image, ImageDraw

    img = solid_background(COLOR_DARK)
    draw = ImageDraw.Draw(img)
    W, H = 1080, 1920

    font_brand = _load_font(64, bold=True)
    font_cta = _load_font(48)
    font_url = _load_font(52, bold=True)
    font_sub = _load_font(36)

    # 골드 선 장식
    draw.rectangle([60, H // 3, W - 60, H // 3 + 4], fill=COLOR_GOLD)
    draw.rectangle([60, H * 2 // 3 + 80, W - 60, H * 2 // 3 + 84], fill=COLOR_GOLD)

    cta = '더 자세한 내용은'
    url = cfg.get('outro_url', 'the4thpath.com')
    follow = cfg.get('outro_cta', '팔로우하면 매일 이런 정보를 받습니다')
    brand = cfg.get('brand_name', 'The 4th Path')

    y = H // 3 + 60
    for text, font, color in [
        (cta, font_cta, COLOR_WHITE),
        (url, font_url, COLOR_GOLD),
        ('', None, None),
        (brand, font_brand, COLOR_WHITE),
        (follow, font_sub, (180, 180, 180)),
    ]:
        if not font:
            y += 40
            continue
        tw, th = _text_size(draw, text, font)
        draw.text(((W - tw) // 2, y), text, font=font, fill=color)
        y += th + 24

    path = str(_tmp_slide('outro'))
    img.save(path)
    return path


# ─── ffmpeg 헬퍼 ──────────────────────────────────────

def _run_ffmpeg(args: list, quiet: bool = False) -> bool:
    cmd = [FFMPEG, '-y'] + args
    if quiet:
        cmd = [FFMPEG, '-y', '-loglevel', 'error'] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        logger.error(f"ffmpeg 오류: {result.stderr[-400:]}")
    return result.returncode == 0


def _check_ffmpeg() -> bool:
    try:
        r = subprocess.run([FFMPEG, '-version'], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def make_clip(slide_png: str, audio_wav: str, output_mp4: str) -> float:
    """
    슬라이드 PNG + 오디오 WAV → MP4 클립 (Ken Burns zoompan).
    Returns: 클립 실제 길이(초)
    """
    duration = get_audio_duration(audio_wav) + 0.3  # 약간 여유

    ok = _run_ffmpeg([
        '-loop', '1', '-i', slide_png,
        '-i', audio_wav,
        '-c:v', 'libx264', '-tune', 'stillimage',
        '-c:a', 'aac', '-b:a', '192k',
        '-pix_fmt', 'yuv420p',
        '-vf', (
            'scale=1080:1920,'
            'zoompan=z=\'min(zoom+0.0003,1.05)\':'
            'x=\'iw/2-(iw/zoom/2)\':'
            'y=\'ih/2-(ih/zoom/2)\':'
            'd=1:s=1080x1920:fps=30'
        ),
        '-shortest',
        '-r', '30',
        output_mp4,
    ], quiet=True)

    return duration if ok else 0.0


def concat_clips_xfade(clips: list[dict], output_mp4: str,
                        transition: str = 'fade', trans_dur: float = 0.5) -> bool:
    """
    여러 클립을 xfade 전환으로 결합.
    clips: [{'video': path, 'audio': path, 'duration': float}, ...]
    """
    if len(clips) < 2:
        return _run_ffmpeg(['-i', clips[0]['mp4'], '-c', 'copy', output_mp4])

    # xfade filter_complex 구성
    n = len(clips)
    inputs = []
    for c in clips:
        inputs += ['-i', c['mp4']]

    # 비디오 xfade 체인
    filter_parts = []
    offset = 0.0
    prev_v = '[0:v]'
    prev_a = '[0:a]'

    for i in range(1, n):
        offset = sum(c['duration'] for c in clips[:i]) - trans_dur * i
        out_v = f'[f{i}v]' if i < n - 1 else '[video]'
        out_a = f'[f{i}a]' if i < n - 1 else '[audio]'
        filter_parts.append(
            f'{prev_v}[{i}:v]xfade=transition={transition}:'
            f'duration={trans_dur}:offset={offset:.3f}{out_v}'
        )
        filter_parts.append(
            f'{prev_a}[{i}:a]acrossfade=d={trans_dur}{out_a}'
        )
        prev_v = out_v
        prev_a = out_a

    filter_complex = '; '.join(filter_parts)

    ok = _run_ffmpeg(
        inputs + [
            '-filter_complex', filter_complex,
            '-map', '[video]', '-map', '[audio]',
            '-c:v', 'libx264', '-c:a', 'aac',
            '-pix_fmt', 'yuv420p',
            output_mp4,
        ]
    )
    return ok


def mix_bgm(video_mp4: str, bgm_path: str, output_mp4: str,
            volume: float = 0.08) -> bool:
    """BGM을 낮은 볼륨으로 믹스"""
    if not Path(bgm_path).exists():
        logger.warning(f"BGM 파일 없음 ({bgm_path}) — BGM 없이 진행")
        import shutil
        shutil.copy2(video_mp4, output_mp4)
        return True
    return _run_ffmpeg([
        '-i', video_mp4,
        '-i', bgm_path,
        '-filter_complex',
        f'[1:a]volume={volume}[bgm];[0:a][bgm]amix=inputs=2:duration=first[a]',
        '-map', '0:v', '-map', '[a]',
        '-c:v', 'copy', '-c:a', 'aac',
        '-shortest',
        output_mp4,
    ])


def burn_subtitles(video_mp4: str, srt_path: str, output_mp4: str) -> bool:
    """SRT 자막 burn-in"""
    font_name = 'NanumGothic'
    # Windows 맑은고딕 폰트명 확인
    for fname in ['NotoSansKR-Regular.ttf', 'malgun.ttf']:
        fp = FONTS_DIR / fname
        if not fp.exists():
            fp = Path(f'C:/Windows/Fonts/{fname}')
        if fp.exists():
            font_name = fp.stem
            break

    style = (
        f'FontName={font_name},'
        'FontSize=22,'
        'PrimaryColour=&H00FFFFFF,'
        'OutlineColour=&H80000000,'
        'BorderStyle=4,'
        'BackColour=&H80000000,'
        'Outline=0,Shadow=0,'
        'MarginV=120,'
        'Alignment=2,'
        'Bold=1'
    )
    # Windows 경로는 subtitles 필터에서 옵션 구분자(:)로 오인될 수 있어
    # filename=... 형태로 명시하고 슬래시/콜론만 ffmpeg 호환 형태로 정규화한다.
    srt_esc = str(srt_path).replace('\\', '/').replace(':', '\\:').replace("'", r"\'")
    return _run_ffmpeg([
        '-i', video_mp4,
        '-vf', f"subtitles=filename='{srt_esc}':force_style='{style}'",
        '-c:v', 'libx264', '-c:a', 'copy',
        output_mp4,
    ])


# ─── SRT 생성 ─────────────────────────────────────────

def build_srt(script_sections: list[dict]) -> str:
    """
    섹션별 자막 생성.
    script_sections: [{'text': str, 'start': float, 'duration': float}, ...]
    """
    lines = []
    for i, section in enumerate(script_sections, 1):
        start = section['start']
        end = start + section['duration']
        # 문장을 2줄로 분할
        text = section['text']
        mid = len(text) // 2
        if len(text) > 30:
            space = text.rfind(' ', 0, mid)
            if space > 0:
                text = text[:space] + '\n' + text[space+1:]
        lines += [str(i), f'{_sec_to_srt(start)} --> {_sec_to_srt(end)}', text, '']
    return '\n'.join(lines)


def _sec_to_srt(s: float) -> str:
    h, rem = divmod(int(s), 3600)
    m, sec = divmod(rem, 60)
    ms = int((s - int(s)) * 1000)
    return f'{h:02d}:{m:02d}:{sec:02d},{ms:03d}'


# ─── 임시 파일 경로 ────────────────────────────────────

_tmp_dir: Optional[Path] = None

def _set_tmp_dir(d: Path):
    global _tmp_dir
    _tmp_dir = d

def _tmp_slide(name: str) -> Path:
    return _tmp_dir / f'slide_{name}.png'

def _tmp_wav(name: str) -> Path:
    return _tmp_dir / f'tts_{name}.wav'

def _tmp_clip(name: str) -> Path:
    return _tmp_dir / f'clip_{name}.mp4'


# ─── 메인 클래스 ──────────────────────────────────────

class ShortsConverter:
    """
    뉴스앵커 포맷 쇼츠 변환기.
    사용:
        sc = ShortsConverter()
        mp4_path = sc.generate(article)
    """

    def __init__(self):
        self.cfg = _load_template()

    def generate(self, article: dict) -> str:
        """메인 파이프라인. Returns: 최종 MP4 경로 또는 ''"""
        import tempfile

        if not _check_ffmpeg():
            logger.error("ffmpeg 없음. PATH 또는 FFMPEG_PATH 확인")
            return ''

        key_points = article.get('key_points', [])
        if not key_points:
            logger.warning("KEY_POINTS 없음 — 쇼츠 생성 불가")
            return ''

        title = article.get('title', '')
        corner = article.get('corner', '쉬운세상')
        slug = article.get('slug', 'article')
        date_str = datetime.now().strftime('%Y%m%d')

        corner_cfg = self.cfg.get('corners', {}).get(corner, {})
        tts_speed = corner_cfg.get('tts_speed', self.cfg.get('tts_speaking_rate_default', 1.05))
        transition = corner_cfg.get('transition', 'fade')
        trans_dur = self.cfg.get('transition_duration', 0.5)
        voice = self.cfg.get('tts_voice_ko', 'ko-KR-Wavenet-A')
        is_oncut = corner == '한컷'
        force_data = corner_cfg.get('force_data_card', False)

        logger.info(f"쇼츠 변환 시작: {title} / {corner}")

        with tempfile.TemporaryDirectory() as tmp:
            _set_tmp_dir(Path(tmp))

            # ── 1. DALL-E 배경 생성 ─────────────────
            bg_prompt = corner_cfg.get('bg_prompt_style')
            bg_img = generate_background_dalle(bg_prompt, corner) if bg_prompt else None

            # ── 2. TTS 스크립트 구성 ────────────────
            title_short = title[:40] + ('...' if len(title) > 40 else '')
            scripts = {
                'intro': f'오늘은 {title_short}에 대해 알아보겠습니다.',
                'headline': f'{title_short}',
            }
            for i, kp in enumerate(key_points[:3], 1):
                scripts[f'point{i}'] = kp
            if force_data or (not is_oncut and len(key_points) > 2):
                scripts['data'] = '관련 데이터를 확인해보겠습니다.'
            scripts['outro'] = (
                f'자세한 내용은 {self.cfg.get("outro_url","the4thpath.com")}에서 확인하세요. '
                '팔로우 부탁드립니다.'
            )

            # ── 3. 슬라이드 합성 ────────────────────
            slides = {
                'intro': compose_intro_slide(self.cfg),
                'headline': compose_headline_slide(article, self.cfg, bg_img),
            }
            for i, kp in enumerate(key_points[:3], 1):
                slides[f'point{i}'] = compose_point_slide(kp, i, article, self.cfg, bg_img)
            if 'data' in scripts:
                slides['data'] = compose_data_slide(article, self.cfg)
            slides['outro'] = compose_outro_slide(self.cfg)

            # ── 4. TTS 합성 + 클립 생성 ──────────────
            clips = []
            for key in scripts:
                wav_path = str(_tmp_wav(key))
                clip_path = str(_tmp_clip(key))
                slide_path = slides.get(key)
                if not slide_path or not Path(slide_path).exists():
                    continue

                ok = synthesize_section(scripts[key], wav_path, voice, tts_speed)
                if not ok:
                    logger.warning(f"TTS 실패: {key} — 슬라이드만 사용")
                    # 무음 WAV 생성 (2초)
                    _run_ffmpeg(['-f', 'lavfi', '-i', 'anullsrc=r=24000:cl=mono',
                                 '-t', '2', wav_path], quiet=True)

                dur = make_clip(slide_path, wav_path, clip_path)
                if dur > 0:
                    clips.append({'mp4': clip_path, 'duration': dur})

            if not clips:
                logger.error("생성된 클립 없음")
                return ''

            # ── 5. 클립 결합 (xfade) ─────────────────
            merged = str(Path(tmp) / 'merged.mp4')
            if len(clips) == 1:
                import shutil
                shutil.copy2(clips[0]['mp4'], merged)
            else:
                if not concat_clips_xfade(clips, merged, transition, trans_dur):
                    logger.error("클립 결합 실패")
                    return ''

            # ── 6. BGM 믹스 ──────────────────────────
            with_bgm = str(Path(tmp) / 'with_bgm.mp4')
            mix_bgm(merged, str(BGM_PATH), with_bgm, self.cfg.get('bgm_volume', 0.08))
            source_for_srt = with_bgm if Path(with_bgm).exists() else merged

            # ── 7. SRT 자막 생성 ─────────────────────
            srt_sections = []
            t = 0.0
            for clip_data in clips:
                srt_sections.append({'text': '', 'start': t, 'duration': clip_data['duration']})
                t += clip_data['duration'] - trans_dur

            # 섹션별 텍스트 채우기
            keys = list(scripts.keys())
            for i, section in enumerate(srt_sections):
                if i < len(keys):
                    section['text'] = scripts[keys[i]]

            srt_content = build_srt([s for s in srt_sections if s['text']])
            srt_path = str(Path(tmp) / 'subtitles.srt')
            Path(srt_path).write_text(srt_content, encoding='utf-8-sig')

            # ── 8. 자막 burn-in ───────────────────────
            output_path = str(OUTPUT_DIR / f'{date_str}_{slug}_shorts.mp4')
            if not burn_subtitles(source_for_srt, srt_path, output_path):
                # 자막 실패 시 자막 없는 버전으로
                import shutil
                shutil.copy2(source_for_srt, output_path)

        logger.info(f"쇼츠 생성 완료: {output_path}")
        return output_path


# ─── 모듈 레벨 진입점 (scheduler 호환) ────────────────

def convert(article: dict, card_path: str = '', save_file: bool = True) -> str:
    """
    scheduler.py/_run_conversion_pipeline()에서 호출하는 진입점.
    card_path: 사용하지 않음 (이전 버전 호환 파라미터)
    """
    sc = ShortsConverter()
    return sc.generate(article)


if __name__ == '__main__':
    sample = {
        'title': 'ChatGPT 처음 쓰는 사람을 위한 완전 가이드',
        'slug': 'chatgpt-shorts-test',
        'corner': '쉬운세상',
        'key_points': [
            '무료로 바로 시작할 수 있다',
            'GPT-3.5도 일반 용도엔 충분하다',
            '프롬프트의 질이 결과를 결정한다',
        ],
        'sources': [{'title': 'OpenAI 공식 블로그', 'url': 'https://openai.com'}],
    }
    sc = ShortsConverter()
    path = sc.generate(sample)
    print(f'완료: {path}')
