"""
bots/shorts/stock_fetcher.py
역할: 스크립트 keywords → 스톡 영상 클립 다운로드 (Pexels → Pixabay → 이미지 폴백)

캐릭터 오버레이:
  manifest.character_overlay.enabled = true 이면
  캐릭터 PNG를 각 클립 우하단에 FFmpeg overlay로 합성.

출력:
  data/shorts/clips/{timestamp}/clip_N.mp4
"""
import json
import logging
import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent

PEXELS_VIDEO_URL = 'https://api.pexels.com/videos/search'
PIXABAY_VIDEO_URL = 'https://pixabay.com/api/videos/'


def _load_config() -> dict:
    cfg_path = BASE_DIR / 'config' / 'shorts_config.json'
    if cfg_path.exists():
        return json.loads(cfg_path.read_text(encoding='utf-8'))
    return {}


def _get_ffmpeg() -> str:
    ffmpeg_env = os.environ.get('FFMPEG_PATH', '')
    if ffmpeg_env and Path(ffmpeg_env).exists():
        return ffmpeg_env
    return 'ffmpeg'


# ─── Pexels ──────────────────────────────────────────────────

def _search_pexels(keyword: str, api_key: str, prefer_vertical: bool = True) -> list[dict]:
    """Pexels Video API 검색 → [{url, width, height, duration}, ...] 반환."""
    import urllib.parse
    import urllib.request

    params = urllib.parse.urlencode({
        'query': keyword,
        'orientation': 'portrait' if prefer_vertical else 'landscape',
        'size': 'medium',
        'per_page': 10,
    })
    req = urllib.request.Request(
        f'{PEXELS_VIDEO_URL}?{params}',
        headers={'Authorization': api_key},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        results = []
        for v in data.get('videos', []):
            # 최적 파일 선택 (HD 이하, portrait 우선)
            best = None
            for vf in v.get('video_files', []):
                if vf.get('quality') in ('hd', 'sd') and vf.get('link', '').endswith('.mp4'):
                    if best is None or (prefer_vertical and vf.get('height', 0) > vf.get('width', 0)):
                        best = vf
            if best:
                results.append({
                    'url': best['link'],
                    'width': best.get('width', 0),
                    'height': best.get('height', 0),
                    'duration': v.get('duration', 5),
                })
        return results
    except Exception as e:
        logger.warning(f'Pexels 검색 실패 ({keyword}): {e}')
        return []


# ─── Pixabay ─────────────────────────────────────────────────

def _search_pixabay(keyword: str, api_key: str, prefer_vertical: bool = True) -> list[dict]:
    """Pixabay Video API 검색 → [{url, width, height, duration}, ...] 반환."""
    import urllib.parse

    params = urllib.parse.urlencode({
        'key': api_key,
        'q': keyword,
        'video_type': 'film',
        'per_page': 10,
    })
    req = urllib.request.Request(f'{PIXABAY_VIDEO_URL}?{params}')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        results = []
        for hit in data.get('hits', []):
            videos = hit.get('videos', {})
            # medium 우선
            for quality in ('medium', 'large', 'small', 'tiny'):
                vf = videos.get(quality)
                if vf and vf.get('url', '').endswith('.mp4'):
                    results.append({
                        'url': vf['url'],
                        'width': vf.get('width', 0),
                        'height': vf.get('height', 0),
                        'duration': hit.get('duration', 5),
                    })
                    break
        return results
    except Exception as e:
        logger.warning(f'Pixabay 검색 실패 ({keyword}): {e}')
        return []


# ─── 다운로드 ─────────────────────────────────────────────────

def _download_clip(url: str, dest: Path) -> bool:
    """URL → dest 파일 다운로드. 성공 시 True."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        dest.write_bytes(data)
        logger.debug(f'클립 다운로드: {dest.name} ({len(data)//1024}KB)')
        return True
    except Exception as e:
        logger.warning(f'클립 다운로드 실패 ({url[:60]}): {e}')
        return False


# ─── FFmpeg 전처리 ────────────────────────────────────────────

def _prepare_clip(input_path: Path, output_path: Path, duration: float = 6.0) -> bool:
    """
    클립을 1080×1920 세로 포맷으로 변환 + 길이 트리밍.
    가로 클립은 center-crop, 세로 클립은 scale.
    """
    ffmpeg = _get_ffmpeg()
    cmd = [
        ffmpeg, '-y',
        '-i', str(input_path),
        '-t', str(duration),
        '-vf', (
            'scale=1080:1920:force_original_aspect_ratio=increase,'
            'crop=1080:1920'
        ),
        '-r', '30',
        '-c:v', 'libx264', '-crf', '23', '-preset', 'fast',
        '-an',  # 스톡 클립 오디오 제거
        str(output_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        return True
    except subprocess.CalledProcessError as e:
        logger.warning(f'클립 전처리 실패: {e.stderr.decode(errors="ignore")[:200]}')
        return False


def _kenburns_image(image_path: Path, output_path: Path, duration: float = 6.0) -> bool:
    """정지 이미지 → Ken Burns 효과 MP4."""
    ffmpeg = _get_ffmpeg()
    frames = int(duration * 30)
    cmd = [
        ffmpeg, '-y',
        '-loop', '1',
        '-i', str(image_path),
        '-vf', (
            f'scale=1200:2134,'
            f'zoompan=z=\'min(zoom+0.0008,1.1)\':'
            f'd={frames}:'
            f'x=\'iw/2-(iw/zoom/2)\':'
            f'y=\'ih/2-(ih/zoom/2)\':'
            f's=1080x1920'
        ),
        '-t', str(duration),
        '-r', '30',
        '-c:v', 'libx264', '-crf', '23', '-preset', 'fast',
        '-an',
        str(output_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        return True
    except subprocess.CalledProcessError as e:
        logger.warning(f'Ken Burns 실패: {e.stderr.decode(errors="ignore")[:200]}')
        return False


# ─── 캐릭터 오버레이 ──────────────────────────────────────────

def _overlay_character(
    clip_path: Path,
    output_path: Path,
    char_png: str,
    char_cfg: dict,
) -> bool:
    """
    클립 우하단에 캐릭터 PNG 오버레이.
    char_cfg: {scale_width, margin_right, margin_bottom}
    """
    if not char_png or not Path(char_png).exists():
        return False

    ffmpeg = _get_ffmpeg()
    scale_w = char_cfg.get('scale_width', 300)
    mr = char_cfg.get('margin_right', 40)
    mb = char_cfg.get('margin_bottom', 250)

    # overlay 위치: 오른쪽 끝 - margin
    overlay_x = f'W-{scale_w}-{mr}'
    overlay_y = f'H-{scale_w * 2}-{mb}'  # 대략적인 높이 추정

    cmd = [
        ffmpeg, '-y',
        '-i', str(clip_path),
        '-i', char_png,
        '-filter_complex', (
            f'[1:v]scale={scale_w}:-1[char];'
            f'[0:v][char]overlay={overlay_x}:{overlay_y}'
        ),
        '-c:v', 'libx264', '-crf', '23', '-preset', 'fast',
        '-an',
        str(output_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        return True
    except subprocess.CalledProcessError as e:
        logger.warning(f'캐릭터 오버레이 실패: {e.stderr.decode(errors="ignore")[:200]}')
        return False


# ─── 메인 엔트리포인트 ────────────────────────────────────────

def fetch_clips(
    script: dict,
    manifest: dict,
    output_dir: Path,
    timestamp: str,
    cfg: Optional[dict] = None,
) -> list[Path]:
    """
    스크립트 keywords → 클립 목록 (1080×1920, 준비 완료).

    Args:
        script:     {keywords, mood, ...}
        manifest:   asset_resolver 결과
        output_dir: data/shorts/clips/
        timestamp:  파일명 prefix
        cfg:        shorts_config.json dict

    Returns:
        [clip_path, ...] — 최소 2개, 최대 5개
    """
    if cfg is None:
        cfg = _load_config()

    clips_dir = output_dir / timestamp
    clips_dir.mkdir(parents=True, exist_ok=True)

    vis_cfg = cfg.get('visuals', {})
    min_clips = vis_cfg.get('min_clips', 3)
    max_clips = vis_cfg.get('max_clips', 5)
    prefer_vertical = vis_cfg.get('prefer_vertical', True)
    pexels_key = os.environ.get(vis_cfg.get('pexels_api_key_env', 'PEXELS_API_KEY'), '')
    pixabay_key = os.environ.get(vis_cfg.get('pixabay_api_key_env', 'PIXABAY_API_KEY'), '')

    char_overlay_cfg = cfg.get('assets', {}).get('character_overlay', {})
    overlay_enabled = char_overlay_cfg.get('enabled', True)

    # 표정 순서: hook/body/closer → 각 세그먼트에 할당
    expressions = manifest.get('expressions', [])
    char_pose = manifest.get('pose', manifest.get('character', {}).get('default_pose', ''))

    result_clips: list[Path] = []

    # 1. 사용자 제공 비디오 클립 (Sora 2 영상 → 워터마크 자동 제거 후 사용)
    from shorts.watermark_remover import remove_if_sora
    for i, user_clip in enumerate(manifest.get('user_clips', [])[:max_clips]):
        src = Path(user_clip)
        # Sora 2 워터마크 제거 (SoraWatermarkCleaner 설치 시 자동 적용)
        src = remove_if_sora(src)
        out = clips_dir / f'clip_{i+1:02d}.mp4'
        if _prepare_clip(src, out):
            result_clips.append(out)

    # 2. 사용자 제공 이미지 → Ken Burns
    for i, user_img in enumerate(manifest.get('user_images', [])[:max_clips]):
        if len(result_clips) >= max_clips:
            break
        out = clips_dir / f'clip_img_{i+1:02d}.mp4'
        if _kenburns_image(Path(user_img), out):
            result_clips.append(out)

    # 3. 캐릭터 에셋 + 배경 합성
    background = manifest.get('background', '')
    if background and Path(background).exists() and len(result_clips) < max_clips:
        # 배경 이미지 → Ken Burns 클립 (표정별 합성)
        for seg_idx, expr_png in enumerate(expressions[:3]):
            if len(result_clips) >= max_clips:
                break
            out_bg = clips_dir / f'clip_bg_{seg_idx+1:02d}.mp4'
            if _kenburns_image(Path(background), out_bg):
                # 표정 오버레이
                if expr_png and Path(expr_png).exists():
                    out_char = clips_dir / f'clip_char_{seg_idx+1:02d}.mp4'
                    if _overlay_character(out_bg, out_char, expr_png, char_overlay_cfg):
                        out_bg.unlink(missing_ok=True)
                        result_clips.append(out_char)
                    else:
                        result_clips.append(out_bg)
                else:
                    result_clips.append(out_bg)

    # 4. Pexels 스톡 클립
    keywords = script.get('keywords', [])
    stock_idx = len(result_clips)
    for keyword in keywords:
        if len(result_clips) >= max_clips:
            break
        if pexels_key:
            videos = _search_pexels(keyword, pexels_key, prefer_vertical)
            for v in videos[:2]:
                if len(result_clips) >= max_clips:
                    break
                stock_idx += 1
                raw = clips_dir / f'raw_{stock_idx:02d}.mp4'
                if _download_clip(v['url'], raw):
                    out = clips_dir / f'clip_stock_{stock_idx:02d}.mp4'
                    if _prepare_clip(raw, out):
                        raw.unlink(missing_ok=True)
                        # 캐릭터 오버레이 (포즈)
                        if overlay_enabled and char_pose and Path(char_pose).exists():
                            out_o = clips_dir / f'clip_o_{stock_idx:02d}.mp4'
                            if _overlay_character(out, out_o, char_pose, char_overlay_cfg):
                                out.unlink(missing_ok=True)
                                result_clips.append(out_o)
                            else:
                                result_clips.append(out)
                        else:
                            result_clips.append(out)
                    else:
                        raw.unlink(missing_ok=True)

    # 5. Pixabay 폴백
    for keyword in keywords:
        if len(result_clips) >= max_clips:
            break
        if pixabay_key:
            videos = _search_pixabay(keyword, pixabay_key, prefer_vertical)
            for v in videos[:2]:
                if len(result_clips) >= max_clips:
                    break
                stock_idx += 1
                raw = clips_dir / f'raw_px_{stock_idx:02d}.mp4'
                if _download_clip(v['url'], raw):
                    out = clips_dir / f'clip_px_{stock_idx:02d}.mp4'
                    if _prepare_clip(raw, out):
                        raw.unlink(missing_ok=True)
                        result_clips.append(out)
                    else:
                        raw.unlink(missing_ok=True)

    # 6. 폴백: 배경 이미지만 있는 단순 클립
    if len(result_clips) < min_clips:
        logger.warning(f'클립 부족 ({len(result_clips)}/{min_clips}) — 배경 반복 폴백')
        fallback_img = Path(background) if background and Path(background).exists() else None
        if not fallback_img:
            # 단색 배경 생성
            fallback_img = clips_dir / 'fallback_bg.png'
            _generate_solid_bg(fallback_img)
        while len(result_clips) < min_clips:
            stock_idx += 1
            out = clips_dir / f'clip_fallback_{stock_idx:02d}.mp4'
            if _kenburns_image(fallback_img, out):
                result_clips.append(out)
            else:
                break

    logger.info(f'클립 준비 완료: {len(result_clips)}개 → {clips_dir}')
    return result_clips[:max_clips]


def _generate_solid_bg(output_path: Path, color: str = '#1a1a2e') -> None:
    """단색 배경 PNG 생성 (Pillow 사용, 없으면 FFmpeg)."""
    try:
        from PIL import Image
        img = Image.new('RGB', (1080, 1920), color)
        img.save(str(output_path))
    except Exception:
        ffmpeg = _get_ffmpeg()
        try:
            subprocess.run(
                [ffmpeg, '-y', '-f', 'lavfi',
                 '-i', f'color=c={color.lstrip("#")}:size=1080x1920:rate=1',
                 '-frames:v', '1', str(output_path)],
                check=True, capture_output=True, timeout=30,
            )
        except Exception as e:
            logger.warning(f'단색 배경 생성 실패: {e}')
