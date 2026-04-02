"""
bots/prompt_layer/video_prompt.py
Format prompts for video generation engines (Kling, Veo).
"""
from .base import BaseComposer, ComposedPrompt
from .visual_vocabulary import VISUAL_STYLE_MODIFIERS, NEGATIVE_TERMS


class KlingPromptFormatter(BaseComposer):
    """
    Format prompts for Kling AI video generation.
    Kling works best with: scene description + movement + mood + negative prompt.
    """

    def compose(self, input_data: dict, engine: str = 'kling_free') -> ComposedPrompt:
        """
        input_data: {
            'scenes': list[dict],  # [{text, type, image_prompt}, ...]
            'corner': str,         # content corner/category
            'duration': float,     # target duration in seconds
        }
        """
        scenes = input_data.get('scenes', [])
        corner = input_data.get('corner', '')

        # Build positive prompt from scenes
        scene_texts = []
        for scene in scenes:
            prompt = scene.get('image_prompt') or scene.get('text', '')
            if prompt:
                scene_texts.append(self._enhance_for_kling(prompt, corner))

        positive = '. '.join(scene_texts[:3])  # Max 3 scenes per prompt
        if not positive:
            positive = f'cinematic short video about {corner or "technology"}'

        # Kling negative prompt
        negative = ', '.join(NEGATIVE_TERMS + ['text overlay', 'subtitles', 'watermark'])

        # Add beat markers for Kling
        positive = f'{positive}. Camera: smooth movement, vertical 9:16 format. Style: cinematic, vibrant.'

        return ComposedPrompt(
            positive=positive,
            negative=negative,
            metadata={'engine': engine, 'corner': corner}
        )

    def _enhance_for_kling(self, text: str, corner: str) -> str:
        """Add cinematic enhancement to prompt."""
        modifiers = ', '.join(VISUAL_STYLE_MODIFIERS[:3])
        return f'{text}, {modifiers}'


class VeoPromptFormatter(BaseComposer):
    """
    Format prompts for Google Veo video generation.
    Veo works best with structured ingredient list format.
    """

    def compose(self, input_data: dict, engine: str = 'veo3') -> ComposedPrompt:
        """
        input_data: same as KlingPromptFormatter
        """
        scenes = input_data.get('scenes', [])
        corner = input_data.get('corner', '')

        scene_texts = [
            scene.get('image_prompt') or scene.get('text', '')
            for scene in scenes if scene.get('image_prompt') or scene.get('text')
        ]

        # Veo structured format: Subject + Action + Setting + Style
        subject = scene_texts[0] if scene_texts else f'{corner or "technology"} concept'
        positive = (
            f'Subject: {subject}. '
            f'Format: vertical 9:16 portrait video. '
            f'Style: cinematic, {", ".join(VISUAL_STYLE_MODIFIERS[:2])}. '
            f'Camera: smooth pan or zoom. Duration: short clip.'
        )

        return ComposedPrompt(
            positive=positive,
            metadata={'engine': engine, 'corner': corner, 'format': 'veo_structured'}
        )
