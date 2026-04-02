"""
bots/prompt_layer/__init__.py
Unified entry point for all prompt composition.

V3.0 scope: video + search + tts categories
V3.1+: expand to all categories
"""
from .base import ComposedPrompt
from .video_prompt import KlingPromptFormatter, VeoPromptFormatter
from .search_query import StockSearchQueryComposer


def compose(category: str, input_data: dict, engine: str) -> 'ComposedPrompt':
    """
    Unified entry point for all prompt composition.

    category: 'video' | 'search' | 'tts' | 'image' | 'writing' | 'caption'
    input_data: category-specific dict
    engine: target engine name

    V3.0 scope: video + search only
    V3.1+: expand to all categories
    """
    composer = _get_composer(category, engine)
    return composer.compose(input_data, engine)


def _get_composer(category: str, engine: str):
    """Return appropriate composer for category+engine combination."""
    if category == 'video':
        if engine in ('kling_free', 'kling_pro'):
            return KlingPromptFormatter()
        else:
            return VeoPromptFormatter()
    elif category == 'search':
        return StockSearchQueryComposer()
    else:
        # Fallback: return a passthrough composer for unsupported categories
        from .base import PassthroughComposer
        return PassthroughComposer()


__all__ = ['compose', 'ComposedPrompt']
