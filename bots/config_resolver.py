"""
bots/config_resolver.py [NEW]

Single source of truth at runtime.
Merges user_profile + engine.json + env.

Priority: user_profile > engine.json > hardcoded defaults
Missing API key → auto-downgrade to free alternative
"""

import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Base directory of the project (one level up from bots/)
BASE_DIR = Path(__file__).resolve().parent.parent

# Fallback engine for each category when all else fails
FALLBACKS = {
    'writing': 'openclaw',
    'tts': 'edge_tts',
    'video': 'ffmpeg_slides',
    'image': 'external',
}

# Budget-to-engine priority lists per category
BUDGET_ENGINE_MAP = {
    'free': {
        'writing': ['openclaw', 'claude_web', 'gemini_web'],
        'tts':     ['kokoro', 'edge_tts'],
        'video':   ['kling_free', 'ffmpeg_slides'],
        'image':   ['external'],
    },
    'low': {
        'writing': ['openclaw', 'claude_web', 'claude'],
        'tts':     ['openai_tts', 'kokoro', 'edge_tts'],
        'video':   ['kling_free', 'veo3', 'seedance2', 'ffmpeg_slides'],
        'image':   ['dalle', 'external'],
    },
    'medium': {
        'writing': ['openclaw', 'claude', 'gemini'],
        'tts':     ['elevenlabs', 'openai_tts', 'cosyvoice2', 'edge_tts'],
        'video':   ['kling_free', 'veo3', 'seedance2', 'runway', 'ffmpeg_slides'],
        'image':   ['dalle', 'external'],
    },
    'premium': {
        'writing': ['openclaw', 'claude', 'gemini'],
        'tts':     ['elevenlabs', 'openai_tts', 'cosyvoice2'],
        'video':   ['kling_free', 'veo3', 'seedance2', 'runway', 'kling_pro'],
        'image':   ['dalle', 'midjourney', 'external'],
    },
}

# Engine registry: local=True means no API key required (free/local)
ENGINE_REGISTRY = {
    'kokoro':        {'local': True},
    'edge_tts':      {'local': True},
    'ffmpeg_slides': {'local': True},
    'external':      {'local': True},
    'cosyvoice2':    {'local': True},
    'openclaw':      {'local': True},
    'claude_web':    {'local': True},
    'gemini_web':    {'local': True},
    # API-based engines
    'elevenlabs':    {'local': False},
    'openai_tts':    {'local': False},
    'claude':        {'local': False},
    'gemini':        {'local': False},
    'kling_free':    {'local': False},
    'kling_pro':     {'local': False},
    'veo3':          {'local': False},
    'seedance2':     {'local': False},
    'runway':        {'local': False},
    'dalle':         {'local': False},
    'midjourney':    {'local': False},
}

# Map from engine name to required environment variable
ENGINE_API_KEY_MAP = {
    'elevenlabs': 'ELEVENLABS_API_KEY',
    'openai_tts': 'OPENAI_API_KEY',
    'claude':     'ANTHROPIC_API_KEY',
    'gemini':     'GEMINI_API_KEY',
    'kling_free': 'KLING_API_KEY',
    'kling_pro':  'KLING_API_KEY',
    'veo3':       'GEMINI_API_KEY',
    'seedance2':  'FAL_API_KEY',
    'runway':     'RUNWAY_API_KEY',
    'dalle':      'OPENAI_API_KEY',
    'midjourney': 'MIDJOURNEY_API_KEY',
}


class ConfigResolver:
    """
    Single source of truth at runtime.
    Merges user_profile + engine.json + env.

    Priority: user_profile > engine.json > hardcoded defaults
    Missing API key → auto-downgrade to free alternative
    """

    def resolve(self) -> dict:
        """Resolve and return the full runtime configuration."""
        profile = self._load('config/user_profile.json')
        engine = self._load('config/engine.json')

        resolved = {
            'writing':   self._resolve_engine('writing', profile),
            'tts':       self._resolve_engine('tts', profile),
            'video':     self._resolve_engine('video', profile),
            'image':     self._resolve_engine('image', profile),
            'platforms': self._resolve_platforms(profile),
            'budget':    profile.get('budget', 'free'),
            'level':     profile.get('level', 'beginner'),
        }
        return resolved

    def _load(self, path: str) -> dict:
        """Load JSON from BASE_DIR/path; return {} if file not found or invalid."""
        full_path = BASE_DIR / path
        try:
            with open(full_path, encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"[설정] {path} 없음 — 기본값 사용", file=sys.stderr)
            return {}
        except json.JSONDecodeError as e:
            print(f"[설정] {path} 파싱 오류: {e} — 기본값 사용", file=sys.stderr)
            return {}

    def _has_api_key(self, engine_name: str) -> bool:
        """
        Check whether the required API key env var for the given engine is set.
        Engines not in ENGINE_API_KEY_MAP are local/free and always available.
        """
        # Local/free engines never need a key
        engine_info = ENGINE_REGISTRY.get(engine_name, {})
        if engine_info.get('local', False):
            return True

        env_var = ENGINE_API_KEY_MAP.get(engine_name)
        if env_var is None:
            # Unknown engine — treat as available (graceful degradation)
            logger.warning(
                "Unknown engine '%s': not in ENGINE_API_KEY_MAP or ENGINE_REGISTRY as local; "
                "treating as available.",
                engine_name,
            )
            return True

        value = os.environ.get(env_var, '').strip()
        return len(value) > 0

    def _resolve_engine(self, category: str, profile: dict) -> dict:
        """
        Resolve the active engine for a category.

        Steps:
        1. Check user's chosen provider from profile
        2. Check if that provider's API key exists in env
        3. If not, auto-switch to next available alternative within budget
        4. If all fail, use hardcoded free fallback

        Returns dict with 'provider' and 'auto_selected' flag.
        """
        budget = profile.get('budget', 'free')
        if budget not in BUDGET_ENGINE_MAP:
            logger.warning(
                "Invalid budget value '%s' from profile; falling back to 'free'.",
                budget,
            )
            budget = 'free'
        candidate_list = BUDGET_ENGINE_MAP[budget].get(category, [])

        # Determine user's preferred provider
        engines_section = profile.get('engines', {})
        category_cfg = engines_section.get(category, {})
        user_provider = category_cfg.get('provider', 'auto') if isinstance(category_cfg, dict) else 'auto'

        # If user explicitly set a provider (not "auto"), try it first
        if user_provider and user_provider != 'auto':
            if self._has_api_key(user_provider):
                print(f"[설정] {category}: 사용자 지정 '{user_provider}' 사용")
                return {'provider': user_provider, 'auto_selected': False}
            else:
                print(f"[설정] {category}: '{user_provider}' API 키 없음 — 자동 선택으로 전환")

        # Auto-select: iterate budget-appropriate candidates in priority order
        for engine_name in candidate_list:
            if self._has_api_key(engine_name):
                auto = (user_provider == 'auto')
                if not auto:
                    print(f"[설정] {category}: '{engine_name}'으로 자동 전환")
                else:
                    print(f"[설정] {category}: 자동 선택 → '{engine_name}'")
                return {'provider': engine_name, 'auto_selected': True}

        # Last resort: hardcoded free fallback
        fallback = FALLBACKS.get(category, 'external')
        print(f"[설정] {category}: 모든 엔진 실패 — 기본 폴백 '{fallback}' 사용")
        return {'provider': fallback, 'auto_selected': True}

    def _resolve_platforms(self, profile: dict) -> list:
        """Return the list of target publishing platforms from user profile."""
        platforms = profile.get('platforms', [])
        if not isinstance(platforms, list):
            return [str(platforms)] if platforms else []
        return platforms


# ---------------------------------------------------------------------------
# Standalone test entry point
# ---------------------------------------------------------------------------

def _run_test():
    """Print resolved config for manual verification."""
    print("=" * 60)
    print("ConfigResolver 테스트 실행")
    print("=" * 60)

    resolver = ConfigResolver()
    config = resolver.resolve()

    print("\n[결과] 런타임 설정:")
    print(json.dumps(config, ensure_ascii=False, indent=2))

    print("\n[요약]")
    print(f"  예산 등급 : {config['budget']}")
    print(f"  사용자 레벨: {config['level']}")
    print(f"  플랫폼   : {config['platforms']}")
    for cat in ('writing', 'tts', 'video', 'image'):
        eng = config[cat]
        flag = '(자동)' if eng.get('auto_selected') else '(지정)'
        print(f"  {cat:10s}: {eng['provider']} {flag}")

    print("=" * 60)
    print("테스트 완료")


if __name__ == '__main__':
    if '--test' in sys.argv:
        _run_test()
    else:
        print("사용법: python -m bots.config_resolver --test")
