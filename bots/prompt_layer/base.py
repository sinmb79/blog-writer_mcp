"""
bots/prompt_layer/base.py
Base types for the prompt layer.
"""
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class ComposedPrompt:
    """
    Unified prompt container returned by all composers.

    Fields used varies by engine:
    - Kling: positive + negative
    - Veo: positive (structured)
    - Search: queries list
    - TTS: processed_text
    """
    positive: str = ''
    negative: str = ''
    queries: list[str] = field(default_factory=list)
    processed_text: str = ''
    metadata: dict = field(default_factory=dict)

    def __bool__(self) -> bool:
        return bool(self.positive or self.queries or self.processed_text)


class BaseComposer:
    """Abstract base for all composers."""
    def compose(self, input_data: dict, engine: str) -> ComposedPrompt:
        raise NotImplementedError


class PassthroughComposer(BaseComposer):
    """Returns input as-is for unsupported categories."""
    def compose(self, input_data: dict, engine: str) -> ComposedPrompt:
        return ComposedPrompt(
            positive=input_data.get('text', ''),
            metadata={'passthrough': True, 'engine': engine}
        )
