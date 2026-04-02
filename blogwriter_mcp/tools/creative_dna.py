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


class CreativeDNA(BaseModel):
    themes: list[str]
    writing_style_summary: str
    emotional_register: str
    structural_tendency: str
    philosophical_worldview: str
    vocabulary_register: str
    forbidden_tones: list[str]
    sample_sentence: str

    def to_prompt_context(self) -> str:
        forbidden = ", ".join(self.forbidden_tones) if self.forbidden_tones else "없음"
        themes = ", ".join(self.themes) if self.themes else "없음"
        return (
            "[창작 DNA 적용]\n"
            "이 글은 다음 세계관과 문체를 자연스럽게 반영해 작성합니다.\n\n"
            f"핵심 주제: {themes}\n"
            f"문체: {self.writing_style_summary}\n"
            f"감성 톤: {self.emotional_register}\n"
            f"구조 경향: {self.structural_tendency}\n"
            f"세계관: {self.philosophical_worldview}\n"
            f"어휘 수준: {self.vocabulary_register}\n"
            f"피해야 할 톤: {forbidden}\n"
            f"예시 문장 분위기: \"{self.sample_sentence}\"\n"
        )


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
        self.config_path.write_text(
            json.dumps(dna.model_dump(), ensure_ascii=False, indent=2),
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
            "당신은 사용자의 예술 취향을 분석해 글쓰기 DNA를 구조화하는 편집자다. "
            "반드시 JSON만 반환하고, 설명 문장은 쓰지 마라."
        )

    @staticmethod
    def _build_prompt(preferences: CreativeDNAInput) -> str:
        payload = preferences.model_dump()
        return (
            "다음 취향 정보를 바탕으로 창작 DNA를 추출해주세요.\n"
            "문체, 감정 결, 구조적 습관, 세계관, 금지 톤을 통합해 판단하세요.\n"
            "반드시 아래 JSON 스키마만 반환하세요.\n\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
            "{\n"
            '  "themes": ["..."],\n'
            '  "writing_style_summary": "...",\n'
            '  "emotional_register": "...",\n'
            '  "structural_tendency": "...",\n'
            '  "philosophical_worldview": "...",\n'
            '  "vocabulary_register": "...",\n'
            '  "forbidden_tones": ["..."],\n'
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

