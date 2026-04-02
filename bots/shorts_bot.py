"""
bots/shorts_bot.py
역할: YouTube Shorts 자동 생산 오케스트레이터

Pipeline:
  0. Asset Resolution (semi_auto: input/ 폴더 체크)
  1. Script Extraction (LLM → 규칙 기반 폴백)
  2. Visual Sourcing (stock_fetcher + character overlay)
  3. TTS Generation (ElevenLabs → Google Cloud → Typecast → Edge TTS)
  4. Caption Rendering (ASS, 단어별 하이라이트)
  5. Video Assembly (FFmpeg)
  6. YouTube Upload (Data API v3)

호출:
  python bots/shorts_bot.py                   — 오늘 미처리 eligible 글 자동 선택
  python bots/shorts_bot.py --slug my-article — 특정 글 지정
  python bots/shorts_bot.py --dry-run         — 업로드 제외 테스트
  python bots/shorts_bot.py --upload path.mp4 -- 이미 렌더링된 영상 업로드
"""
import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / '.env')

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / 'bots'))

DATA_DIR = BASE_DIR / 'data'
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'shorts.log', encoding='utf-8'),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


# ─── 결과 타입 ────────────────────────────────────────────────

@dataclass
class ShortsResult:
    success: bool
    article_id: str = ''
    video_path: Optional[str] = None
    youtube_url: Optional[str] = None
    error: Optional[str] = None
    steps_completed: list[str] = field(default_factory=list)


# ─── 설정 로드 ────────────────────────────────────────────────

def _load_config() -> dict:
    cfg_path = BASE_DIR / 'config' / 'shorts_config.json'
    if cfg_path.exists():
        return json.loads(cfg_path.read_text(encoding='utf-8'))
    return {}


# ─── 글 선택 ──────────────────────────────────────────────────

def pick_article(cfg: dict) -> Optional[dict]:
    """
    eligible 글 중 최신 1개 선택.
    기준: corner in corners_eligible, quality_score >= 75, 아직 쇼츠 미변환.
    """
    eligible_corners = set(cfg.get('corners_eligible', []))
    published_dir = DATA_DIR / 'published'
    originals_dir = DATA_DIR / 'originals'

    # 발행된 글 목록 (published/ 폴더)
    candidates = []
    for d in (published_dir, originals_dir):
        if d.exists():
            candidates.extend(d.glob('*.json'))

    if not candidates:
        logger.info('선택 가능한 글 없음')
        return None

    # 이미 변환된 글 목록
    converted = _get_converted_ids()

    results = []
    for f in sorted(candidates, reverse=True):  # 최신 순
        try:
            article = json.loads(f.read_text(encoding='utf-8'))
            slug = article.get('slug', f.stem)
            corner = article.get('corner', '')
            quality = article.get('quality_score', 0)

            if slug in converted:
                continue
            if corner not in eligible_corners:
                continue
            if quality < 75:
                continue

            results.append(article)
        except Exception:
            continue

    if not results:
        logger.info('eligible 글 없음 (corner 또는 quality_score 기준 미충족)')
        return None

    logger.info(f'선택된 글: {results[0].get("title", "")} (corner={results[0].get("corner", "")})')
    return results[0]


def _get_converted_ids() -> set[str]:
    """이미 쇼츠 변환된 article_id 집합."""
    published_dir = DATA_DIR / 'shorts' / 'published'
    if not published_dir.exists():
        return set()
    ids = set()
    for f in published_dir.glob('*.json'):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            if aid := data.get('article_id'):
                ids.add(aid)
        except Exception:
            pass
    return ids


def _is_converted(article_id: str) -> bool:
    return article_id in _get_converted_ids()


# ─── 파이프라인 ───────────────────────────────────────────────

def produce(article: dict, dry_run: bool = False, cfg: Optional[dict] = None) -> ShortsResult:
    """
    블로그 글 → 쇼츠 영상 생산 + (선택) YouTube 업로드.

    Args:
        article:  article dict
        dry_run:  True이면 렌더링까지만 (업로드 생략)
        cfg:      shorts_config.json dict (None이면 자동 로드)

    Returns:
        ShortsResult
    """
    from shorts.asset_resolver import resolve
    from shorts.script_extractor import extract_script
    from shorts.stock_fetcher import fetch_clips
    from shorts.tts_engine import generate_tts
    from shorts.caption_renderer import render_captions
    from shorts.video_assembler import assemble

    if cfg is None:
        cfg = _load_config()

    if not cfg.get('enabled', True):
        return ShortsResult(success=False, error='shorts_bot disabled in config')

    article_id = article.get('slug', 'unknown')
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    result = ShortsResult(success=False, article_id=article_id)

    # 데이터 디렉터리
    scripts_dir = DATA_DIR / 'shorts' / 'scripts'
    clips_dir = DATA_DIR / 'shorts' / 'clips'
    tts_dir = DATA_DIR / 'shorts' / 'tts'
    captions_dir = DATA_DIR / 'shorts' / 'captions'
    rendered_dir = DATA_DIR / 'shorts' / 'rendered'

    try:
        # ── STEP 0: Asset Resolution ─────────────────────────────
        logger.info(f'[{article_id}] STEP 0: Asset Resolution')
        manifest = resolve(article, script=None, cfg=cfg)
        result.steps_completed.append('asset_resolve')

        # ── STEP 1: Script Extraction ────────────────────────────
        logger.info(f'[{article_id}] STEP 1: Script Extraction')
        script = extract_script(article, scripts_dir, ts, cfg=cfg, manifest=manifest)
        # manifest 업데이트 (mood 반영)
        manifest = resolve(article, script=script, cfg=cfg)
        result.steps_completed.append('script_extract')

        # ── STEP 2: Visual Sourcing ──────────────────────────────
        logger.info(f'[{article_id}] STEP 2: Visual Sourcing')
        clips = fetch_clips(script, manifest, clips_dir, ts, cfg=cfg)
        if len(clips) < cfg.get('visuals', {}).get('min_clips', 2):
            raise RuntimeError(f'클립 부족: {len(clips)}개')
        result.steps_completed.append('visual_fetch')

        # ── STEP 3: TTS Generation ───────────────────────────────
        logger.info(f'[{article_id}] STEP 3: TTS Generation')
        tts_wav, timestamps = generate_tts(script, tts_dir, ts, cfg=cfg)

        # 사용자 제공 오디오가 있으면 교체
        if manifest.get('audio_source') == 'user_provided' and manifest.get('user_audio'):
            from pathlib import Path as P
            user_audio = P(manifest['user_audio'])
            if user_audio.exists():
                import shutil
                tts_wav = tts_dir / f'{ts}.wav'
                if user_audio.suffix.lower() == '.wav':
                    shutil.copy2(user_audio, tts_wav)
                else:
                    # mp3 → wav 변환
                    from shorts.tts_engine import _mp3_to_wav
                    _mp3_to_wav(user_audio, tts_wav)
                # Whisper로 타임스탬프 재추출
                from shorts.tts_engine import _whisper_timestamps
                timestamps = _whisper_timestamps(tts_wav)
                logger.info('사용자 제공 오디오 사용')

        result.steps_completed.append('tts_generate')

        # ── STEP 4: Caption Rendering ────────────────────────────
        logger.info(f'[{article_id}] STEP 4: Caption Rendering')
        from shorts.tts_engine import _get_wav_duration
        wav_dur = _get_wav_duration(tts_wav)
        ass_path = render_captions(script, timestamps, captions_dir, ts, wav_dur, cfg=cfg)
        result.steps_completed.append('caption_render')

        # ── STEP 5: Video Assembly ───────────────────────────────
        logger.info(f'[{article_id}] STEP 5: Video Assembly')
        video_path = assemble(clips, tts_wav, ass_path, rendered_dir, ts, cfg=cfg)
        result.video_path = str(video_path)
        result.steps_completed.append('video_assemble')

        # commit input/_processed 이동
        manifest_commit = resolve(article, script=script, cfg=cfg, commit_processed=True)

        # ── STEP 6: YouTube Upload ───────────────────────────────
        if dry_run:
            logger.info(f'[{article_id}] STEP 6: 건너뜀 (dry-run)')
            result.success = True
            return result

        logger.info(f'[{article_id}] STEP 6: YouTube Upload')
        from shorts.youtube_uploader import upload
        upload_record = upload(video_path, article, script, ts, cfg=cfg)
        result.youtube_url = upload_record.get('url', '')
        result.steps_completed.append('youtube_upload')

        result.success = True
        logger.info(f'[{article_id}] 쇼츠 생산 완료: {result.youtube_url}')
        return result

    except Exception as e:
        logger.error(f'[{article_id}] 쇼츠 생산 실패 (단계: {result.steps_completed}): {e}')
        result.error = str(e)
        return result


def upload_existing(video_path: str, article_id: str = '', cfg: Optional[dict] = None) -> ShortsResult:
    """
    이미 렌더링된 MP4를 YouTube에 업로드.
    article과 script는 data/published/ 또는 data/originals/에서 slug로 찾음.
    """
    from shorts.youtube_uploader import upload

    if cfg is None:
        cfg = _load_config()

    vp = Path(video_path)
    if not vp.exists():
        return ShortsResult(success=False, error=f'파일 없음: {video_path}')

    # article 로드
    article = {}
    script = {}
    if article_id:
        for d in (DATA_DIR / 'published', DATA_DIR / 'originals', DATA_DIR / 'shorts' / 'scripts'):
            for f in d.glob(f'*{article_id}*.json'):
                try:
                    data = json.loads(f.read_text(encoding='utf-8'))
                    if d.name == 'scripts' or 'scripts' in str(d):
                        script = data
                    else:
                        article = data
                    break
                except Exception:
                    pass

    ts = vp.stem
    try:
        record = upload(vp, article, script, ts, cfg=cfg)
        return ShortsResult(
            success=True,
            article_id=article_id,
            video_path=video_path,
            youtube_url=record.get('url', ''),
            steps_completed=['youtube_upload'],
        )
    except Exception as e:
        return ShortsResult(success=False, error=str(e))


# ─── CLI ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='YouTube Shorts 자동 생산 봇')
    parser.add_argument('--slug', type=str, help='특정 글 slug 지정')
    parser.add_argument('--dry-run', action='store_true', help='업로드 제외 테스트')
    parser.add_argument('--upload', type=str, metavar='VIDEO_PATH', help='이미 렌더링된 MP4 업로드')
    parser.add_argument('--article-id', type=str, default='', help='--upload와 함께 article_id 지정')
    args = parser.parse_args()

    cfg = _load_config()

    # 렌더링된 영상 업로드 모드
    if args.upload:
        result = upload_existing(args.upload, args.article_id, cfg)
        if result.success:
            print(f'[완료] 업로드 성공: {result.youtube_url}')
            sys.exit(0)
        else:
            print(f'[오류] 업로드 실패: {result.error}', file=sys.stderr)
            sys.exit(1)

    # 글 선택
    if args.slug:
        # slug로 글 찾기
        article = None
        for d in (DATA_DIR / 'published', DATA_DIR / 'originals'):
            if not d.exists():
                continue
            for f in d.glob(f'*{args.slug}*.json'):
                try:
                    article = json.loads(f.read_text(encoding='utf-8'))
                    break
                except Exception:
                    pass
            if article:
                break
        if not article:
            print(f'[오류] slug "{args.slug}" 에 해당하는 글 없음', file=sys.stderr)
            sys.exit(1)
    else:
        article = pick_article(cfg)
        if not article:
            print('[완료] 처리할 eligible 글 없음')
            sys.exit(0)

    result = produce(article, dry_run=args.dry_run, cfg=cfg)

    if result.success:
        if args.dry_run:
            print(f'[완료 dry-run] 영상: {result.video_path}')
            print(f'완료 단계: {", ".join(result.steps_completed)}')
        else:
            print(f'[완료] 업로드: {result.youtube_url}')
        sys.exit(0)
    else:
        print(f'[오류] {result.error}', file=sys.stderr)
        print(f'완료 단계: {", ".join(result.steps_completed)}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
