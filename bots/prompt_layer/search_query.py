"""
bots/prompt_layer/search_query.py
Compose stock video/image search queries from Korean concepts.
"""
from .base import BaseComposer, ComposedPrompt
from .visual_vocabulary import CONCEPT_TO_VISUAL, VISUAL_STYLE_MODIFIERS
import re


class StockSearchQueryComposer(BaseComposer):
    """
    Korean concept -> English visual search terms.
    Used to search Pexels/Pixabay/Unsplash for stock footage.
    """

    def compose(self, input_data: dict, engine: str = 'pexels') -> ComposedPrompt:
        """
        input_data: {
            'sentence': str,  # Korean sentence to find visuals for
            'platform': str,  # 'pexels' | 'pixabay' | 'kling' | 'veo'
            'count': int,     # number of search queries to return (default 3)
        }
        Returns ComposedPrompt with queries list
        """
        sentence = input_data.get('sentence', '')
        count = input_data.get('count', 3)

        queries = self._sentence_to_queries(sentence, count)

        return ComposedPrompt(
            queries=queries,
            metadata={'sentence': sentence, 'engine': engine}
        )

    def _sentence_to_queries(self, sentence: str, count: int) -> list[str]:
        """Extract Korean concepts from sentence and map to visual search terms."""
        # Find matching concepts from vocabulary
        matched_visuals = []
        for concept, visuals in CONCEPT_TO_VISUAL.items():
            if concept in sentence:
                matched_visuals.extend(visuals)

        # If no matches, use generic professional stock footage terms
        if not matched_visuals:
            matched_visuals = ['professional business', 'modern lifestyle', 'technology future']

        # Return up to count unique queries
        seen = set()
        unique = []
        for v in matched_visuals:
            if v not in seen:
                seen.add(v)
                unique.append(v)

        return unique[:count]
