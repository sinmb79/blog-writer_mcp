from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, Field

from bots.engine_loader import EngineLoader


BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CREATIVE_DNA_PATH = BASE_DIR / "config" / "creative_dna.json"


class CreativeDNAInput(BaseModel):
    favorite_authors: list[str] = Field(default_factory=list)
    favorite_books: list[str] = Field(default_factory=list)
    favorite_films: list[str] = Field(default_factory=list)
    favorite_anime_style: list[str] = Field(default_factory=list)
    favorite_music: list[str] = Field(default_factory=list)
    personal_keywords: list[str] = Field(default_factory=list)
    additional_context: str = ""


class NarrativeDNA(BaseModel):
    opening_hook: str = "Start from a familiar scene before widening into meaning."
    tension_engine: str = "Hold the deeper meaning back long enough for curiosity to build."
    signature_move: str = "Cross lived reality with symbolic reflection."
    resolution_pattern: str = "End with a calm realization instead of a loud summary."


class CreativeDNA(BaseModel):
    themes: list[str]
    writing_style_summary: str
    emotional_register: str
    structural_tendency: str
    philosophical_worldview: str
    vocabulary_register: str
    narrative_dna: NarrativeDNA = Field(default_factory=NarrativeDNA)
    forbidden_tones: list[str]
    key_prop_tendency: str = ""
    sample_sentence: str

    def to_prompt_context(self, include_narrative: bool = True) -> str:
        forbidden = ", ".join(self.forbidden_tones) if self.forbidden_tones else "none"
        themes = ", ".join(self.themes) if self.themes else "none"
        lines = [
            "[Creative DNA Applied]",
            "Write the article so the voice feels organic and internally consistent, not imitative.",
            "",
            f"Themes: {themes}",
            f"Writing style: {self.writing_style_summary}",
            f"Emotional register: {self.emotional_register}",
            f"Structural tendency: {self.structural_tendency}",
            f"Philosophical worldview: {self.philosophical_worldview}",
            f"Vocabulary register: {self.vocabulary_register}",
            f"Forbidden tones: {forbidden}",
            f"Sample sentence mood: \"{self.sample_sentence}\"",
        ]

        if include_narrative:
            lines.extend(
                [
                    f"Opening hook: {self.narrative_dna.opening_hook}",
                    f"Tension engine: {self.narrative_dna.tension_engine}",
                    f"Signature move: {self.narrative_dna.signature_move}",
                    f"Resolution pattern: {self.narrative_dna.resolution_pattern}",
                    f"Key prop tendency: {self.key_prop_tendency or 'Use a concrete object to carry emotional meaning.'}",
                ]
            )

        return "\n".join(lines) + "\n"


class CreativeDNAManager:
    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or DEFAULT_CREATIVE_DNA_PATH

    def load(self) -> CreativeDNA | None:
        if not self.config_path.exists():
            return None
        data = json.loads(self.config_path.read_text(encoding="utf-8"))
        if "extracted_dna" in data:
            data = data["extracted_dna"]
        return CreativeDNA.model_validate(data)

    def save(self, dna: CreativeDNA) -> CreativeDNA:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"extracted_dna": dna.model_dump()}
        self.config_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return dna

    def analyze_and_save(self, preferences: CreativeDNAInput, writer=None) -> CreativeDNA:
        writer = writer or EngineLoader().get_writer()
        prompt = self._build_prompt(preferences)
        raw = writer.write(prompt, system=self._system_prompt())
        dna = CreativeDNA.model_validate(self._extract_json(raw))
        return self.save(dna)

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You analyze a user's artistic preferences and extract a structured Creative DNA profile. "
            "Return JSON only. Do not include any explanation outside the JSON object."
        )

    @staticmethod
    def _build_prompt(preferences: CreativeDNAInput) -> str:
        payload = preferences.model_dump()
        return (
            "Analyze the following creative preferences and extract a reusable writing DNA profile.\n"
            "Capture style, emotional register, structural tendency, worldview, forbidden tones, "
            "and a narrative DNA block describing how this writer tends to open, sustain tension, "
            "perform a signature move, and resolve a piece.\n"
            "Also infer how this voice tends to use a concrete object or prop to carry emotion.\n"
            "Return only JSON in the following shape.\n\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            "{\n"
            '  "themes": ["..."],\n'
            '  "writing_style_summary": "...",\n'
            '  "emotional_register": "...",\n'
            '  "structural_tendency": "...",\n'
            '  "philosophical_worldview": "...",\n'
            '  "vocabulary_register": "...",\n'
            '  "narrative_dna": {\n'
            '    "opening_hook": "...",\n'
            '    "tension_engine": "...",\n'
            '    "signature_move": "...",\n'
            '    "resolution_pattern": "..."\n'
            "  },\n"
            '  "forbidden_tones": ["..."],\n'
            '  "key_prop_tendency": "...",\n'
            '  "sample_sentence": "..."\n'
            "}"
        )

    @staticmethod
    def _extract_json(raw: str) -> dict:
        raw = raw.strip()
        if raw.startswith("{"):
            return json.loads(raw)
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            raise ValueError("Creative DNA response did not contain JSON.")
        return json.loads(match.group(0))
