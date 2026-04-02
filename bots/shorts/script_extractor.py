"""
bots/shorts/script_extractor.py
역할: 블로그 포스트 dict → 쇼츠용 스크립트 JSON 생성

LLM 우선순위:
  1. OpenClaw (로컬, EngineLoader 경유)
  2. Claude API (ANTHROPIC_API_KEY)
  폴백: 제목+KEY_POINTS 기반 규칙 기반 추출

출력:
  data/shorts/scripts/{timestamp}.json
  {hook, body, closer, keywords, mood, originality_check, article_id}
"""
import json
import logging
import re
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent
PROMPT_TEMPLATE_PATH = BASE_DIR / 'templates' / 'shorts' / 'extract_prompt.txt'


# ─── 유틸 ────────────────────────────────────────────────────

def _load_config() -> dict:
    cfg_path = BASE_DIR / 'config' / 'shorts_config.json'
    if cfg_path.exists():
        return json.loads(cfg_path.read_text(encoding='utf-8'))
    return {}


def _build_post_text(article: dict) -> str:
    """article dict → LLM에 전달할 블로그 본문 텍스트."""
    title = article.get('title', '')
    key_points = article.get('key_points', article.get('KEY_POINTS', []))
    body_html = article.get('body', article.get('BODY', ''))

    # HTML 태그 제거 (간단한 정규식)
    body_plain = re.sub(r'<[^>]+>', ' ', body_html)
    body_plain = re.sub(r'\s+', ' ', body_plain).strip()
    # 너무 길면 잘라냄 (LLM 토큰 절약)
    if len(body_plain) > 1500:
        body_plain = body_plain[:1500] + '...'

    lines = [f'제목: {title}']
    if key_points:
        if isinstance(key_points, list):
            lines.append('핵심 포인트:')
            lines.extend(f'- {p}' for p in key_points)
        else:
            lines.append(f'핵심 포인트: {key_points}')
    if body_plain:
        lines.append(f'본문: {body_plain}')
    return '\n'.join(lines)


def _load_prompt_template() -> str:
    if PROMPT_TEMPLATE_PATH.exists():
        return PROMPT_TEMPLATE_PATH.read_text(encoding='utf-8')
    # 인라인 폴백
    return (
        'You are a YouTube Shorts script writer for a Korean tech blog.\n'
        'Given the blog post below, extract a 15-20 second Shorts script.\n\n'
        'OUTPUT FORMAT (JSON only):\n'
        '{{"hook":"...","body":["..."],"closer":"...","keywords":["..."],'
        '"mood":"...","originality_check":"..."}}\n\n'
        'BLOG POST:\n---\n{blog_post_content}\n---'
    )


def _parse_json_response(raw: str) -> Optional[dict]:
    """LLM 응답에서 JSON 추출 (마크다운 코드블록 포함 대응)."""
    # ```json ... ``` 블록 제거
    raw = re.sub(r'```json\s*', '', raw)
    raw = re.sub(r'```\s*', '', raw)
    raw = raw.strip()

    # JSON 부분만 추출
    match = re.search(r'\{[\s\S]+\}', raw)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def _validate_script(script: dict) -> bool:
    """필수 필드 존재 + 최소 품질 검사."""
    required = ['hook', 'body', 'closer', 'keywords', 'mood']
    if not all(k in script for k in required):
        return False
    if not script.get('hook'):
        return False
    if not isinstance(script.get('body'), list) or len(script['body']) == 0:
        return False
    # originality_check 없으면 경고만
    if not script.get('originality_check'):
        logger.warning('originality_check 필드 없음 — 스크립트 고유성 검증 불가')
    return True


def _check_template_similarity(new_script: dict, scripts_dir: Path) -> bool:
    """
    직전 10개 스크립트와 본문 단어 중복률 체크.
    60% 초과 → True (유사도 과다, 거부 권고)
    """
    new_words = set(' '.join(new_script.get('body', [])).split())
    if not new_words:
        return False

    history_files = sorted(scripts_dir.glob('*.json'), reverse=True)[:10]
    for hf in history_files:
        try:
            old = json.loads(hf.read_text(encoding='utf-8'))
            old_words = set(' '.join(old.get('body', [])).split())
            if not old_words:
                continue
            overlap = len(new_words & old_words) / len(new_words)
            if overlap > 0.6:
                logger.warning(f'스크립트 유사도 과다 ({overlap:.0%}): {hf.name}')
                return True
        except Exception:
            continue
    return False


# ─── LLM 호출 ────────────────────────────────────────────────

def _extract_via_engine(post_text: str, cfg: dict) -> Optional[dict]:
    """EngineLoader (OpenClaw/Claude API)로 스크립트 추출."""
    sys.path.insert(0, str(BASE_DIR / 'bots'))
    try:
        from engine_loader import EngineLoader
    except ImportError:
        return None

    template = _load_prompt_template()
    prompt = template.replace('{blog_post_content}', post_text)

    system = (
        'You are a YouTube Shorts script extraction assistant. '
        'Output only valid JSON, no explanation.'
    )

    try:
        writer = EngineLoader(cfg_override={'writing': cfg.get('script', {}).get('llm_provider', 'openclaw')}).get_writer()
        raw = writer.write(prompt, system=system).strip()
        return _parse_json_response(raw)
    except Exception as e:
        logger.warning(f'EngineLoader 스크립트 추출 실패: {e}')
        return None


def _extract_via_claude_api(post_text: str) -> Optional[dict]:
    """Anthropic API 직접 호출 (폴백)."""
    import os
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        template = _load_prompt_template()
        prompt = template.replace('{blog_post_content}', post_text)

        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=512,
            messages=[{'role': 'user', 'content': prompt}],
        )
        raw = msg.content[0].text
        return _parse_json_response(raw)
    except Exception as e:
        logger.warning(f'Claude API 스크립트 추출 실패: {e}')
        return None


def _extract_rule_based(article: dict) -> dict:
    """
    LLM 없을 때 규칙 기반 스크립트 추출 (최소 품질 보장).
    제목 → hook, KEY_POINTS → body, CTA → closer.
    """
    title = article.get('title', '제목 없음')
    key_points = article.get('key_points', article.get('KEY_POINTS', []))
    corner = article.get('corner', '')

    if isinstance(key_points, str):
        key_points = [kp.strip('- ').strip() for kp in key_points.split('\n') if kp.strip()]

    # hook: 제목을 의문문으로 변환
    hook = title
    if not hook.endswith('?'):
        hook = f'{title[:20]}... 알고 계셨나요?'

    # body: KEY_POINTS 앞 3개
    body = [p.strip('- ').strip() for p in key_points[:3]] if key_points else [title]

    # closer: 코너별 CTA
    cta_map = {
        '쉬운세상': '블로그에서 더 자세히 확인해보세요.',
        '숨은보물': '이 꿀팁, 주변에 공유해보세요.',
        '웹소설': '전편 블로그에서 읽어보세요.',
    }
    closer = cta_map.get(corner, '구독하고 다음 편도 기대해주세요.')

    # keywords: 제목 명사 추출 (간단)
    keywords = [w for w in re.findall(r'[가-힣A-Za-z]{2,}', title)][:5]
    if not keywords:
        keywords = ['technology', 'korea', 'blog']

    return {
        'hook': hook,
        'body': body,
        'closer': closer,
        'keywords': keywords,
        'mood': 'upbeat',
        'originality_check': f'{title}에 대한 핵심 포인트 요약',
    }


# ─── 메인 엔트리포인트 ────────────────────────────────────────

def extract_script(
    article: dict,
    output_dir: Path,
    timestamp: str,
    cfg: Optional[dict] = None,
    manifest: Optional[dict] = None,
) -> dict:
    """
    블로그 포스트 → 쇼츠 스크립트 생성 + 저장.

    Args:
        article:    article dict (title, body, key_points, corner 등)
        output_dir: data/shorts/scripts/
        timestamp:  파일명 prefix
        cfg:        shorts_config.json dict
        manifest:   asset_resolver 결과 (script_source 확인용)

    Returns:
        script dict {hook, body, closer, keywords, mood, originality_check, article_id}
    """
    if cfg is None:
        cfg = _load_config()

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f'{timestamp}.json'

    article_id = article.get('slug', timestamp)

    # 1. Semi-auto: input/scripts/ 에 사용자 제공 스크립트 있으면 로드
    if manifest and manifest.get('script_source') == 'user_provided':
        user_script_path = manifest.get('user_script_path')
        if user_script_path and Path(user_script_path).exists():
            script = json.loads(Path(user_script_path).read_text(encoding='utf-8'))
            script['article_id'] = article_id
            logger.info(f'사용자 제공 스크립트 사용: {user_script_path}')
            output_path.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding='utf-8')
            return script

    # 2. LLM 추출
    post_text = _build_post_text(article)
    script = None

    # OpenClaw/EngineLoader 시도
    script = _extract_via_engine(post_text, cfg)

    # Claude API 폴백
    if not script or not _validate_script(script):
        logger.info('Claude API 스크립트 추출 시도...')
        script = _extract_via_claude_api(post_text)

    # 규칙 기반 폴백
    if not script or not _validate_script(script):
        logger.warning('LLM 스크립트 추출 실패 — 규칙 기반 폴백 사용')
        script = _extract_rule_based(article)

    if not _validate_script(script):
        raise RuntimeError('스크립트 검증 실패 — 필수 필드 누락')

    # 유사도 검사
    if _check_template_similarity(script, output_dir):
        logger.warning('스크립트 유사도 과다 — 재추출 시도')
        # 한 번 더 시도 (다른 엔진)
        retry = _extract_via_claude_api(post_text)
        if retry and _validate_script(retry) and not _check_template_similarity(retry, output_dir):
            script = retry

    script['article_id'] = article_id

    output_path.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding='utf-8')
    logger.info(f'스크립트 저장: {output_path.name}')
    logger.debug(f'hook: {script.get("hook")} | mood: {script.get("mood")}')
    return script


def load_script(script_path: Path) -> dict:
    """저장된 스크립트 JSON 로드."""
    return json.loads(script_path.read_text(encoding='utf-8'))
