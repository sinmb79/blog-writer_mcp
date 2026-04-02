"""
novel_shorts_converter.py
소설 연재 파이프라인 — 에피소드 KEY_SCENES → 쇼츠 영상 생성 모듈
역할: key_scenes 3개를 기반으로 engine.json 설정에 따라 영상 생성
출력: data/novels/{novel_id}/shorts/ep{N:03d}_shorts.mp4

지원 모드:
  ffmpeg_slides  — DALL-E 이미지 + TTS + Pillow 슬라이드 (기본, 비용 0원)
  seedance       — Seedance 2.0 API로 시네마틱 영상 생성 (유료)
"""
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / '.env')

BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR / 'bots'))
sys.path.insert(0, str(BASE_DIR / 'bots' / 'converters'))

logger = logging.getLogger(__name__)

FFMPEG = os.getenv('FFMPEG_PATH', 'ffmpeg')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
SEEDANCE_API_KEY = os.getenv('SEEDANCE_API_KEY', '')

# ─── EngineLoader / fallback ─────────────────────────────────────────────────

try:
    from engine_loader import EngineLoader as _EngineLoader
    _engine_loader_available = True
except ImportError:
    _engine_loader_available = False


def _make_fallback_writer():
    """engine_loader 없을 때 anthropic SDK 직접 사용"""
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY', ''))

    class _DirectWriter:
        def write(self, prompt: str, system: str = '') -> str:
            msg = client.messages.create(
                model='claude-opus-4-6',
                max_tokens=500,
                system=system or '당신은 한국어 연재소설 작가입니다.',
                messages=[{'role': 'user', 'content': prompt}],
            )
            return msg.content[0].text

    return _DirectWriter()


# shorts_converter 유틸 임포트 (재사용)
try:
    from shorts_converter import (
        make_clip,
        concat_clips_xfade,
        mix_bgm,
        burn_subtitles,
        synthesize_section,
        solid_background,
        _load_font,
        _text_size,
        _draw_gradient_overlay,
    )
    _shorts_utils_available = True
except ImportError:
    _shorts_utils_available = False
    logger.warning("shorts_converter 임포트 실패 — ffmpeg_slides 모드 제한됨")


# ─── 이미지 생성 헬퍼 ─────────────────────────────────────────────────────────

def _generate_dalle_image(prompt: str, save_path: str) -> bool:
    """DALL-E 3로 장면 이미지 생성 (1024×1792)"""
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY 없음 — 단색 배경 사용")
        return False
    try:
        import io
        import requests as req
        from openai import OpenAI
        from PIL import Image

        client = OpenAI(api_key=OPENAI_API_KEY)
        full_prompt = prompt + ' No text, no letters, no numbers, no watermarks. Vertical 9:16 cinematic.'
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
        img = img.resize((1080, 1920))
        img.save(save_path)
        logger.info(f"DALL-E 이미지 생성: {save_path}")
        return True
    except Exception as e:
        logger.warning(f"DALL-E 이미지 생성 실패: {e}")
        return False


def _make_solid_slide(save_path: str, color=(10, 10, 13)):
    """단색 슬라이드 PNG 생성"""
    try:
        from PIL import Image
        img = Image.new('RGB', (1080, 1920), color)
        img.save(save_path)
    except Exception as e:
        logger.error(f"단색 슬라이드 생성 실패: {e}")


def _make_text_slide(save_path: str, text: str, bg_color=(10, 10, 13),
                     accent_color=(200, 168, 78)):
    """텍스트 오버레이 슬라이드 PNG 생성"""
    try:
        from PIL import Image, ImageDraw
        img = Image.new('RGB', (1080, 1920), bg_color)
        draw = ImageDraw.Draw(img)
        W, H = 1080, 1920

        # 상단 강조선
        draw.rectangle([0, 0, W, 6], fill=accent_color)

        # 텍스트
        font = _load_font(52, bold=True) if _shorts_utils_available else None
        if font:
            words = text.split()
            lines = []
            current = ''
            for word in words:
                test = (current + ' ' + word).strip()
                w, _ = _text_size(draw, test, font)
                if w <= W - 120:
                    current = test
                else:
                    if current:
                        lines.append(current)
                    current = word
            if current:
                lines.append(current)

            y = H // 2 - len(lines) * 60 // 2
            for line in lines[:5]:
                lw, lh = _text_size(draw, line, font)
                draw.text(((W - lw) // 2, y), line, font=font, fill=(255, 255, 255))
                y += lh + 16

        # 하단 강조선
        draw.rectangle([0, H - 6, W, H], fill=accent_color)
        img.save(save_path)
    except Exception as e:
        logger.error(f"텍스트 슬라이드 생성 실패: {e}")


# ─── Seedance API 헬퍼 ────────────────────────────────────────────────────────

def _call_seedance_api(prompt: str, duration: str = '10s',
                        resolution: str = '1080x1920') -> str:
    """
    Seedance 2.0 API 호출 → 영상 다운로드 후 임시 경로 반환.
    실패 시 '' 반환.
    """
    if not SEEDANCE_API_KEY:
        logger.warning("SEEDANCE_API_KEY 없음 — seedance 모드 불가")
        return ''
    try:
        import requests as req
        # engine.json에서 api_url 읽기
        engine_config_path = BASE_DIR / 'config' / 'engine.json'
        api_url = 'https://api.seedance2.ai/v1/generate'
        if engine_config_path.exists():
            cfg = json.loads(engine_config_path.read_text(encoding='utf-8'))
            api_url = (cfg.get('video_generation', {})
                       .get('options', {})
                       .get('seedance', {})
                       .get('api_url', api_url))

        headers = {
            'Authorization': f'Bearer {SEEDANCE_API_KEY}',
            'Content-Type': 'application/json',
        }
        payload = {
            'prompt': prompt,
            'resolution': resolution,
            'duration': duration,
            'audio': True,
        }
        logger.info(f"Seedance API 요청: {prompt[:80]}...")
        resp = req.post(api_url, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        # 영상 URL 파싱 (실제 API 응답 구조에 따라 조정 필요)
        video_url = data.get('url') or data.get('video_url') or data.get('output')
        if not video_url:
            logger.error(f"Seedance 응답에 URL 없음: {data}")
            return ''

        # 영상 다운로드
        tmp_path = tempfile.mktemp(suffix='.mp4')
        video_resp = req.get(video_url, timeout=180)
        video_resp.raise_for_status()
        Path(tmp_path).write_bytes(video_resp.content)
        logger.info(f"Seedance 영상 다운로드 완료: {tmp_path}")
        return tmp_path

    except Exception as e:
        logger.error(f"Seedance API 호출 실패: {e}")
        return ''


def _run_ffmpeg(args: list) -> bool:
    """ffmpeg 실행 헬퍼"""
    cmd = [FFMPEG, '-y', '-loglevel', 'error'] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            logger.error(f"ffmpeg 오류: {result.stderr[-400:]}")
        return result.returncode == 0
    except Exception as e:
        logger.error(f"ffmpeg 실행 실패: {e}")
        return False


def _get_clip_duration(mp4_path: str) -> float:
    """ffprobe로 영상 길이(초) 측정"""
    try:
        import subprocess
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json',
             '-show_format', mp4_path],
            capture_output=True, text=True, timeout=10
        )
        data = json.loads(result.stdout)
        return float(data['format']['duration'])
    except Exception:
        return 10.0


# ─── 테마 색상 헬퍼 ───────────────────────────────────────────────────────────

_GENRE_COLORS = {
    'sci-fi':    {'bg': (10, 15, 30),  'accent': (0, 188, 212)},
    'thriller':  {'bg': (10, 10, 13),  'accent': (191, 58, 58)},
    'fantasy':   {'bg': (15, 10, 30),  'accent': (200, 168, 78)},
    'romance':   {'bg': (255, 245, 240), 'accent': (216, 90, 48)},
    'default':   {'bg': (10, 10, 13),  'accent': (200, 168, 78)},
}

def _genre_colors(genre: str) -> dict:
    genre_lower = genre.lower()
    for key in _GENRE_COLORS:
        if key in genre_lower:
            return _GENRE_COLORS[key]
    return _GENRE_COLORS['default']


# ─── NovelShortsConverter ────────────────────────────────────────────────────

class NovelShortsConverter:
    """소설 에피소드 key_scenes → 쇼츠 MP4 생성"""

    def __init__(self, engine=None):
        """engine: EngineLoader 인스턴스 (없으면 내부에서 결정)"""
        if engine is not None:
            self.engine = engine
        elif _engine_loader_available:
            self.engine = _EngineLoader()
        else:
            self.engine = None

        # video_generation provider 결정
        self.video_provider = self._get_video_provider()

        # 번역용 writer (씬 → 영어 프롬프트)
        if self.engine is not None:
            try:
                self.writer = self.engine.get_writer()
            except Exception:
                self.writer = _make_fallback_writer()
        else:
            self.writer = _make_fallback_writer()

    def _get_video_provider(self) -> str:
        """engine.json에서 video_generation.provider 읽기"""
        try:
            cfg_path = BASE_DIR / 'config' / 'engine.json'
            if cfg_path.exists():
                cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
                return cfg.get('video_generation', {}).get('provider', 'ffmpeg_slides')
        except Exception:
            pass
        return 'ffmpeg_slides'

    # ── 공개 API ──────────────────────────────────────────────────────────────

    def generate(self, episode: dict, novel_config: dict) -> str:
        """
        episode의 key_scenes 3개로 쇼츠 생성.
        반환: MP4 경로 (data/novels/{novel_id}/shorts/ep{N:03d}_shorts.mp4)
        실패 시 '' 반환.
        """
        novel_id = novel_config.get('novel_id', episode.get('novel_id', 'unknown'))
        ep_num = episode.get('episode_num', 0)
        key_scenes = episode.get('key_scenes', [])

        if not key_scenes:
            logger.error(f"[{novel_id}] key_scenes 없음 — 쇼츠 생성 불가")
            return ''

        # 출력 디렉터리 준비
        shorts_dir = BASE_DIR / 'data' / 'novels' / novel_id / 'shorts'
        shorts_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(shorts_dir / f'ep{ep_num:03d}_shorts.mp4')

        logger.info(f"[{novel_id}] 에피소드 {ep_num} 쇼츠 생성 시작 (모드: {self.video_provider})")

        try:
            if self.video_provider == 'seedance' and SEEDANCE_API_KEY:
                result = self._generate_seedance(episode, novel_config, output_path)
            else:
                if self.video_provider == 'seedance':
                    logger.warning("SEEDANCE_API_KEY 없음 — ffmpeg_slides 모드로 대체")
                result = self._generate_ffmpeg_slides(episode, novel_config, output_path)

            if result:
                logger.info(f"[{novel_id}] 쇼츠 생성 완료: {output_path}")
            else:
                logger.error(f"[{novel_id}] 쇼츠 생성 실패")

            return output_path if result else ''

        except Exception as e:
            logger.error(f"[{novel_id}] 쇼츠 생성 중 예외: {e}")
            return ''

    # ── ffmpeg_slides 모드 ────────────────────────────────────────────────────

    def _generate_ffmpeg_slides(self, episode: dict, novel_config: dict,
                                  output_path: str) -> bool:
        """
        ffmpeg_slides 모드:
        인트로 슬라이드 + key_scene 1~3 (DALL-E 이미지 + TTS) + 아웃트로 + concat
        """
        if not _shorts_utils_available:
            logger.error("shorts_converter 유틸 없음 — ffmpeg_slides 불가")
            return False

        novel_id = novel_config.get('novel_id', '')
        ep_num = episode.get('episode_num', 0)
        key_scenes = episode.get('key_scenes', [])
        hook = episode.get('hook', '')
        title_ko = novel_config.get('title_ko', '')
        genre = novel_config.get('genre', '')
        colors = _genre_colors(genre)
        bg_color = colors['bg']
        accent_color = colors['accent']

        # 임시 작업 디렉터리
        tmp_dir = Path(tempfile.mkdtemp(prefix=f'novel_{novel_id}_ep{ep_num}_'))

        try:
            clips = []

            # ── 인트로 슬라이드 (소설 제목 + 에피소드 번호) ──────────────────
            intro_slide = str(tmp_dir / 'intro.png')
            intro_text = f"{title_ko}\n{ep_num}화"
            _make_text_slide(intro_slide, f"{title_ko}  ·  {ep_num}화",
                             bg_color, accent_color)
            intro_audio = str(tmp_dir / 'intro.wav')
            synthesize_section(f"{title_ko} {ep_num}화", intro_audio,
                               'ko-KR-Wavenet-A', 1.0)
            intro_mp4 = str(tmp_dir / 'intro.mp4')
            dur = make_clip(intro_slide, intro_audio, intro_mp4)
            if dur > 0:
                clips.append({'mp4': intro_mp4, 'duration': dur})

            # ── key_scene 슬라이드 1~3 ────────────────────────────────────────
            images_dir = BASE_DIR / 'data' / 'novels' / novel_id / 'images'
            images_dir.mkdir(parents=True, exist_ok=True)

            for i, scene in enumerate(key_scenes[:3], 1):
                if not scene:
                    continue

                # DALL-E 이미지 (또는 텍스트 슬라이드 폴백)
                scene_slide = str(tmp_dir / f'scene{i}.png')
                img_prompt = self._scene_to_image_prompt(scene, novel_config)
                img_generated = _generate_dalle_image(img_prompt, scene_slide)
                if not img_generated:
                    _make_text_slide(scene_slide, scene, bg_color, accent_color)

                # 생성된 이미지를 data/images에도 저장 (캐릭터 일관성 참조용)
                perm_img = str(images_dir / f'ep{ep_num:03d}_scene{i}.png')
                if img_generated and Path(scene_slide).exists():
                    import shutil
                    shutil.copy2(scene_slide, perm_img)

                # TTS
                scene_audio = str(tmp_dir / f'scene{i}.wav')
                synthesize_section(scene, scene_audio, 'ko-KR-Wavenet-A', 1.0)

                # 클립 생성
                scene_mp4 = str(tmp_dir / f'scene{i}.mp4')
                dur = make_clip(scene_slide, scene_audio, scene_mp4)
                if dur > 0:
                    clips.append({'mp4': scene_mp4, 'duration': dur})

            # ── 아웃트로 슬라이드 (훅 문장 + 다음 에피소드 예고) ──────────────
            outro_slide = str(tmp_dir / 'outro.png')
            outro_text = hook if hook else '다음 회를 기대해 주세요'
            _make_text_slide(outro_slide, outro_text, bg_color, accent_color)
            outro_audio = str(tmp_dir / 'outro.wav')
            synthesize_section(outro_text, outro_audio, 'ko-KR-Wavenet-A', 1.0)
            outro_mp4 = str(tmp_dir / 'outro.mp4')
            dur = make_clip(outro_slide, outro_audio, outro_mp4)
            if dur > 0:
                clips.append({'mp4': outro_mp4, 'duration': dur})

            if not clips:
                logger.error("생성된 클립 없음")
                return False

            # ── 클립 결합 ────────────────────────────────────────────────────
            concat_mp4 = str(tmp_dir / 'concat.mp4')
            ok = concat_clips_xfade(clips, concat_mp4, transition='fade', trans_dur=0.5)
            if not ok:
                logger.error("클립 결합 실패")
                return False

            # ── BGM 믹스 ─────────────────────────────────────────────────────
            bgm_path = str(BASE_DIR / 'assets' / 'bgm.mp3')
            bgm_mp4 = str(tmp_dir / 'bgm_mixed.mp4')
            mix_bgm(concat_mp4, bgm_path, bgm_mp4, volume=0.08)
            final_source = bgm_mp4 if Path(bgm_mp4).exists() else concat_mp4

            # ── 최종 출력 복사 ────────────────────────────────────────────────
            import shutil
            shutil.copy2(final_source, output_path)
            return True

        except Exception as e:
            logger.error(f"ffmpeg_slides 생성 중 예외: {e}")
            return False
        finally:
            # 임시 파일 정리
            try:
                import shutil
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass

    # ── seedance 모드 ─────────────────────────────────────────────────────────

    def _generate_seedance(self, episode: dict, novel_config: dict,
                            output_path: str) -> bool:
        """
        seedance 모드:
        key_scene → 영어 Seedance 프롬프트 변환 → API 호출 → 클립 concat
        인트로2초 + 씬10초×3 + 아웃트로3초 = 35초 구성
        """
        novel_id = novel_config.get('novel_id', '')
        ep_num = episode.get('episode_num', 0)
        key_scenes = episode.get('key_scenes', [])
        hook = episode.get('hook', '')
        title_ko = novel_config.get('title_ko', '')
        genre = novel_config.get('genre', '')
        colors = _genre_colors(genre)
        bg_color = colors['bg']
        accent_color = colors['accent']

        tmp_dir = Path(tempfile.mkdtemp(prefix=f'novel_seedance_{novel_id}_ep{ep_num}_'))

        try:
            clip_paths = []

            # ── 인트로 슬라이드 (2초, 정적 이미지) ──────────────────────────
            intro_slide = str(tmp_dir / 'intro.png')
            _make_text_slide(intro_slide, f"{title_ko}  ·  {ep_num}화",
                             bg_color, accent_color)
            intro_mp4 = str(tmp_dir / 'intro.mp4')
            if _run_ffmpeg([
                '-loop', '1', '-i', intro_slide,
                '-c:v', 'libx264', '-t', '2',
                '-pix_fmt', 'yuv420p',
                '-vf', 'scale=1080:1920',
                intro_mp4,
            ]):
                clip_paths.append({'mp4': intro_mp4, 'duration': 2.0})

            # ── key_scene 클립 (Seedance 10초×3) ─────────────────────────────
            for i, scene in enumerate(key_scenes[:3], 1):
                if not scene:
                    continue
                en_prompt = self._scene_to_seedance_prompt(scene, novel_config)
                seedance_mp4 = _call_seedance_api(en_prompt, duration='10s')

                if seedance_mp4 and Path(seedance_mp4).exists():
                    # 영구 저장
                    images_dir = BASE_DIR / 'data' / 'novels' / novel_id / 'images'
                    images_dir.mkdir(parents=True, exist_ok=True)
                    perm_clip = str(images_dir / f'ep{ep_num:03d}_scene{i}_seedance.mp4')
                    import shutil
                    shutil.copy2(seedance_mp4, perm_clip)
                    clip_paths.append({'mp4': seedance_mp4, 'duration': 10.0})
                else:
                    # Seedance 실패 시 DALL-E 슬라이드 폴백
                    logger.warning(f"장면 {i} Seedance 실패 — 이미지 슬라이드 대체")
                    fallback_slide = str(tmp_dir / f'scene{i}_fallback.png')
                    img_prompt = self._scene_to_image_prompt(scene, novel_config)
                    img_ok = _generate_dalle_image(img_prompt, fallback_slide)
                    if not img_ok:
                        _make_text_slide(fallback_slide, scene, bg_color, accent_color)
                    fallback_mp4 = str(tmp_dir / f'scene{i}_fallback.mp4')
                    if _run_ffmpeg([
                        '-loop', '1', '-i', fallback_slide,
                        '-c:v', 'libx264', '-t', '10',
                        '-pix_fmt', 'yuv420p',
                        '-vf', 'scale=1080:1920',
                        fallback_mp4,
                    ]):
                        clip_paths.append({'mp4': fallback_mp4, 'duration': 10.0})

            # ── 아웃트로 (3초, 정적 이미지) ──────────────────────────────────
            outro_slide = str(tmp_dir / 'outro.png')
            outro_text = hook if hook else '다음 회를 기대해 주세요'
            _make_text_slide(outro_slide, outro_text, bg_color, accent_color)
            outro_mp4 = str(tmp_dir / 'outro.mp4')
            if _run_ffmpeg([
                '-loop', '1', '-i', outro_slide,
                '-c:v', 'libx264', '-t', '3',
                '-pix_fmt', 'yuv420p',
                '-vf', 'scale=1080:1920',
                outro_mp4,
            ]):
                clip_paths.append({'mp4': outro_mp4, 'duration': 3.0})

            if not clip_paths:
                logger.error("Seedance 모드: 생성된 클립 없음")
                return False

            # ── concat (xfade) ────────────────────────────────────────────────
            if _shorts_utils_available:
                concat_mp4 = str(tmp_dir / 'concat.mp4')
                ok = concat_clips_xfade(clip_paths, concat_mp4,
                                        transition='fade', trans_dur=0.5)
            else:
                # 단순 concat fallback
                concat_mp4 = str(tmp_dir / 'concat.mp4')
                list_file = str(tmp_dir / 'clips.txt')
                with open(list_file, 'w') as f:
                    for c in clip_paths:
                        f.write(f"file '{c['mp4']}'\n")
                ok = _run_ffmpeg([
                    '-f', 'concat', '-safe', '0', '-i', list_file,
                    '-c', 'copy', concat_mp4,
                ])

            if not ok:
                logger.error("클립 결합 실패")
                return False

            import shutil
            shutil.copy2(concat_mp4, output_path)
            return True

        except Exception as e:
            logger.error(f"Seedance 모드 생성 중 예외: {e}")
            return False
        finally:
            try:
                import shutil
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass

    # ── 프롬프트 변환 메서드 ──────────────────────────────────────────────────

    def _scene_to_seedance_prompt(self, scene: str, novel_config: dict) -> str:
        """한국어 장면 묘사 → 영어 Seedance 프롬프트 변환"""
        genre = novel_config.get('genre', 'thriller')
        atmosphere = novel_config.get('setting', {}).get('atmosphere', '')

        prompt = f"""다음 한국어 소설 장면 묘사를 Seedance 2.0 AI 영상 생성용 영어 프롬프트로 변환하세요.

장르: {genre}
분위기: {atmosphere}
장면: {scene}

변환 규칙:
- 영어로만 작성
- 시각적이고 구체적인 묘사 (인물, 배경, 조명, 날씨, 카메라 움직임)
- 분위기 키워드 포함 (cinematic, neo-noir 등 장르에 맞게)
- "9:16 vertical" 포함
- No text overlays, no watermarks
- 3~5문장, 100단어 이내

영어 프롬프트만 출력 (설명 없이):"""

        try:
            result = self.writer.write(prompt, system='You are a cinematic AI video prompt engineer.')
            return result.strip()
        except Exception as e:
            logger.error(f"Seedance 프롬프트 변환 실패: {e}")
            # 폴백: 간단 번역 구조
            genre_key = 'neo-noir sci-fi' if 'sci-fi' in genre else genre
            return (
                f"Cinematic scene: {scene[:80]}. "
                f"{genre_key} atmosphere. "
                f"Dramatic lighting, rain-soaked streets of Seoul 2040. "
                f"Vertical 9:16 cinematic shot. No text, no watermarks."
            )

    def _scene_to_sora_prompt(self, scene: str, novel_config: dict, duration: int = 15) -> str:
        """한국어 소설 장면 → Sora 2 구조화 프롬프트 (검증된 서식 적용)"""
        import sys
        sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent / 'shorts'))
        from prompt_builder import llm_sora_prompt

        genre = novel_config.get('genre', 'thriller')
        atmosphere = novel_config.get('setting', {}).get('atmosphere', 'cinematic')
        return llm_sora_prompt(
            scene_text=scene,
            genre=genre,
            atmosphere=atmosphere,
            writer=self.writer,
            duration=duration,
            has_dialogue=True,
        )

    def _scene_to_image_prompt(self, scene: str, novel_config: dict) -> str:
        """DALL-E용 이미지 프롬프트 생성"""
        genre = novel_config.get('genre', 'thriller')
        world = novel_config.get('setting', {}).get('world', '')
        atmosphere = novel_config.get('setting', {}).get('atmosphere', '')

        prompt = f"""소설 장면 묘사를 DALL-E 3 이미지 생성용 영어 프롬프트로 변환하세요.

세계관: {world}
분위기: {atmosphere}
장면: {scene}

규칙:
- 영어, 2~3문장
- 세로형(1024×1792) 구도
- 장르({genre})에 맞는 분위기
- No text, no letters, no watermarks

영어 프롬프트만 출력:"""

        try:
            result = self.writer.write(prompt, system='You are a visual prompt engineer for DALL-E.')
            return result.strip()
        except Exception as e:
            logger.error(f"이미지 프롬프트 변환 실패: {e}")
            return (
                f"Cinematic vertical illustration: {scene[:80]}. "
                f"Dark atmospheric lighting. "
                f"No text, no watermarks. Vertical 9:16."
            )


# ─── 직접 실행 테스트 ─────────────────────────────────────────────────────────

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s [%(levelname)s] %(message)s')

    sample_config = json.loads(
        (BASE_DIR / 'config' / 'novels' / 'shadow-protocol.json')
        .read_text(encoding='utf-8')
    )
    sample_episode = {
        'novel_id': 'shadow-protocol',
        'episode_num': 1,
        'title': '프로토콜',
        'body': '테스트 본문',
        'hook': '아리아의 목소리가 처음으로 떨렸다.',
        'key_scenes': [
            '서진이 비 내리는 서울 골목을 뛰어가는 장면',
            '아리아가 빨간 경고 메시지를 출력하는 장면',
            '감시 드론이 서진의 아파트 창문 밖을 맴도는 장면',
        ],
        'summary': '서진이 그림자 프로토콜을 발견한다.',
        'generated_at': '2026-03-26T00:00:00+00:00',
    }

    converter = NovelShortsConverter()
    output = converter.generate(sample_episode, sample_config)
    print(f"결과: {output}")
