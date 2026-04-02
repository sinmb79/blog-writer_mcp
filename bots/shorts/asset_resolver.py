"""
bots/shorts/asset_resolver.py
역할: 각 파이프라인 단계에서 사용할 에셋 소스를 결정하고
      resolution_manifest.json을 생성.

Semi-auto 우선순위:
  input/{scripts,images,videos,audio}/{article_id}* 파일 체크
  → 있으면 user_provided, 없으면 auto

캐릭터 결정:
  article.corner → shorts_config corner_character_map → character type
  → character assets 경로 결정

출력:
  resolution_manifest.json (메모리 dict로 반환, 필요시 저장)
"""
import json
import logging
import re
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent

EXPRESSION_MOOD_MAP = {
    'dramatic':   ['surprised', 'thinking', 'determined'],
    'upbeat':     ['curious',   'explaining', 'smiling'],
    'mysterious': ['curious',   'thinking', 'smiling'],
    'calm':       ['explaining','thinking', 'smiling'],
}

SEGMENT_EXPRESSION = {
    'hook':   0,   # index into mood expression list
    'body':   1,
    'closer': 2,
}


def _load_config() -> dict:
    cfg_path = BASE_DIR / 'config' / 'shorts_config.json'
    if cfg_path.exists():
        return json.loads(cfg_path.read_text(encoding='utf-8'))
    return {}


def _normalize_id(article_id: str) -> str:
    """slug/article_id → 파일명 접두사 비교용 문자열."""
    return re.sub(r'[^a-z0-9_\-]', '', article_id.lower())


# ─── Input 폴더 스캔 ─────────────────────────────────────────

def _scan_input(article_id: str, cfg: dict) -> dict:
    """
    input/ 폴더에서 article_id와 매칭되는 사용자 제공 파일 탐색.
    Returns: {script: path|None, images: [path], videos: [path], audio: path|None}
    """
    input_dirs = cfg.get('input_dirs', {})
    norm_id = _normalize_id(article_id)

    found = {'script': None, 'images': [], 'videos': [], 'audio': None}

    # scripts
    scripts_dir = BASE_DIR / input_dirs.get('scripts', 'input/scripts/')
    if scripts_dir.exists():
        for f in scripts_dir.glob('*.json'):
            if _normalize_id(f.stem).startswith(norm_id) or f.stem == article_id:
                found['script'] = str(f)
                break
        if not found['script']:
            # FIFO 소비: 가장 오래된 파일
            files = sorted(scripts_dir.glob('*.json'))
            if files:
                found['script'] = str(files[0])

    # images
    images_dir = BASE_DIR / input_dirs.get('images', 'input/images/')
    if images_dir.exists():
        matched = [f for f in sorted(images_dir.glob('*.png'))
                   if _normalize_id(f.stem).startswith(norm_id)]
        matched += [f for f in sorted(images_dir.glob('*.jpg'))
                    if _normalize_id(f.stem).startswith(norm_id)]
        if matched:
            found['images'] = [str(f) for f in matched]
        else:
            # FIFO: 매칭 없으면 순서대로 소비
            all_imgs = sorted((images_dir.glob('*.png'))) + sorted(images_dir.glob('*.jpg'))
            if all_imgs:
                found['images'] = [str(f) for f in all_imgs[:5]]

    # videos
    videos_dir = BASE_DIR / input_dirs.get('videos', 'input/videos/')
    if videos_dir.exists():
        matched = [f for f in sorted(videos_dir.glob('*.mp4'))
                   if _normalize_id(f.stem).startswith(norm_id)]
        if matched:
            found['videos'] = [str(f) for f in matched]
        else:
            all_vids = sorted(videos_dir.glob('*.mp4'))
            if all_vids:
                found['videos'] = [str(f) for f in all_vids[:5]]

    # audio
    audio_dir = BASE_DIR / input_dirs.get('audio', 'input/audio/')
    if audio_dir.exists():
        for ext in ('*.wav', '*.mp3'):
            for f in sorted(audio_dir.glob(ext)):
                if _normalize_id(f.stem).startswith(norm_id) or f.stem == article_id:
                    found['audio'] = str(f)
                    break
            if found['audio']:
                break
        if not found['audio']:
            # FIFO
            for ext in ('*.wav', '*.mp3'):
                files = sorted(audio_dir.glob(ext))
                if files:
                    found['audio'] = str(files[0])
                    break

    return found


def _move_to_processed(paths: list[str]) -> None:
    """처리 완료 파일을 input/_processed/ 로 이동."""
    if not paths:
        return
    processed = BASE_DIR / 'input' / '_processed'
    processed.mkdir(parents=True, exist_ok=True)
    for p in paths:
        src = Path(p)
        if src.exists():
            dst = processed / src.name
            try:
                shutil.move(str(src), str(dst))
                logger.debug(f'처리 완료 이동: {src.name} → input/_processed/')
            except Exception as e:
                logger.warning(f'파일 이동 실패 ({src.name}): {e}')


# ─── 캐릭터 결정 ──────────────────────────────────────────────

def _resolve_character(article: dict, cfg: dict) -> dict:
    """
    article.corner → character type → assets 경로.
    Returns: {type, name, display_name, default_pose, poses_dir, expressions_dir, backgrounds_dir, ...}
    """
    corner = article.get('corner', '')
    corner_map = cfg.get('assets', {}).get('corner_character_map', {})
    char_type = corner_map.get(corner, 'tech_blog')

    characters = cfg.get('assets', {}).get('characters', {})
    char_cfg = characters.get(char_type, characters.get('tech_blog', {}))

    return {
        'type': char_type,
        'name': char_cfg.get('name', 'bao'),
        'display_name': char_cfg.get('display_name', '바오'),
        'default_pose': str(BASE_DIR / char_cfg.get('default_pose', '')),
        'poses_dir': str(BASE_DIR / char_cfg.get('poses_dir', '')),
        'expressions_dir': str(BASE_DIR / char_cfg.get('expressions_dir', '')),
        'backgrounds_dir': str(BASE_DIR / char_cfg.get('backgrounds_dir', '')),
        'scarves_dir': str(BASE_DIR / char_cfg.get('scarves_dir', '')) if 'scarves_dir' in char_cfg else None,
    }


def _pick_pose(char_info: dict, mood: str) -> str:
    """mood 기반 포즈 선택 (poses_dir 내 파일)."""
    poses_dir = Path(char_info['poses_dir'])
    if not poses_dir.exists():
        return char_info['default_pose']

    pose_files = sorted(poses_dir.glob('*.png'))
    if not pose_files:
        return char_info['default_pose']

    mood_pose_map = {
        'dramatic':   'pose_explaining',
        'upbeat':     'pose_waving',
        'mysterious': 'pose_thinking',
        'calm':       'pose_sitting',
    }
    preferred = mood_pose_map.get(mood, '')
    for pf in pose_files:
        if preferred and preferred in pf.stem:
            return str(pf)
    return str(pose_files[0])


def _pick_expressions(char_info: dict, mood: str) -> list[str]:
    """훅/본문/클로저 각각 표정 파일 경로 선택."""
    expr_dir = Path(char_info['expressions_dir'])
    if not expr_dir.exists():
        return [char_info['default_pose']] * 3

    expr_files = {f.stem: str(f) for f in expr_dir.glob('*.png')}
    if not expr_files:
        return [char_info['default_pose']] * 3

    mood_exprs = EXPRESSION_MOOD_MAP.get(mood, ['curious', 'explaining', 'smiling'])
    result = []
    for expr_name in mood_exprs:
        # 완전 일치 또는 접두사 일치
        match = next((v for k, v in expr_files.items() if expr_name in k), None)
        if not match:
            match = list(expr_files.values())[0]
        result.append(match)
    return result


def _pick_background(char_info: dict) -> str:
    """캐릭터 타입에 맞는 배경 파일 선택 (첫 번째 파일)."""
    bg_dir = Path(char_info['backgrounds_dir'])
    if not bg_dir.exists():
        return ''
    bg_files = sorted(bg_dir.glob('*.png')) + sorted(bg_dir.glob('*.jpg'))
    return str(bg_files[0]) if bg_files else ''


# ─── 메인 엔트리포인트 ────────────────────────────────────────

def resolve(
    article: dict,
    script: Optional[dict] = None,
    cfg: Optional[dict] = None,
    commit_processed: bool = False,
) -> dict:
    """
    에셋 소스 결정 → resolution manifest 생성.

    Args:
        article:           article dict (slug, corner 등)
        script:            이미 추출된 스크립트 (mood 결정용)
        cfg:               shorts_config.json dict
        commit_processed:  True이면 사용된 input/ 파일을 _processed/로 이동

    Returns:
        manifest dict:
        {
          script_source:   "auto" | "user_provided",
          visual_source:   "auto" | "user_provided" | "mixed",
          audio_source:    "auto" | "user_provided",
          character: {type, name, display_name, default_pose, poses_dir, ...},
          pose:            "path/to/pose.png",
          expressions:     ["path/to/expr1.png", ...],  # [hook, body, closer]
          background:      "path/to/bg.png",
          user_script_path: str | None,
          user_clips:      [str, ...],   # mp4 경로
          user_images:     [str, ...],   # png/jpg 경로
          user_audio:      str | None,
        }
    """
    if cfg is None:
        cfg = _load_config()

    article_id = article.get('slug', article.get('article_id', 'unknown'))
    mood = (script or {}).get('mood', 'upbeat')
    production_mode = cfg.get('production_mode', 'auto')

    manifest = {
        'article_id': article_id,
        'production_mode': production_mode,
        'script_source': 'auto',
        'visual_source': 'auto',
        'audio_source': 'auto',
        'user_script_path': None,
        'user_clips': [],
        'user_images': [],
        'user_audio': None,
    }

    # Semi-auto: input/ 폴더 스캔
    if production_mode == 'semi_auto':
        found = _scan_input(article_id, cfg)

        if found['script']:
            manifest['script_source'] = 'user_provided'
            manifest['user_script_path'] = found['script']

        if found['videos']:
            manifest['visual_source'] = 'user_provided'
            manifest['user_clips'] = found['videos']
        elif found['images']:
            manifest['visual_source'] = 'user_provided'
            manifest['user_images'] = found['images']

        if manifest['user_clips'] and manifest['user_images']:
            manifest['visual_source'] = 'mixed'

        if found['audio']:
            manifest['audio_source'] = 'user_provided'
            manifest['user_audio'] = found['audio']

        logger.info(
            f'에셋 결정 (semi_auto): '
            f'script={manifest["script_source"]}, '
            f'visual={manifest["visual_source"]}, '
            f'audio={manifest["audio_source"]}'
        )
    else:
        logger.info('에셋 결정 (auto): 모든 에셋 자동 생성')

    # 캐릭터 결정
    char_info = _resolve_character(article, cfg)
    pose = _pick_pose(char_info, mood)
    expressions = _pick_expressions(char_info, mood)
    background = _pick_background(char_info)

    manifest['character'] = char_info
    manifest['pose'] = pose
    manifest['expressions'] = expressions
    manifest['background'] = background

    # 처리된 input/ 파일 이동
    if commit_processed and production_mode == 'semi_auto':
        to_move = []
        if manifest['user_script_path']:
            to_move.append(manifest['user_script_path'])
        to_move.extend(manifest['user_clips'])
        to_move.extend(manifest['user_images'])
        if manifest['user_audio']:
            to_move.append(manifest['user_audio'])
        _move_to_processed(to_move)

    return manifest
