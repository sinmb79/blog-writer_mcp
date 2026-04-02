import json
from pathlib import Path

from blogwriter_mcp.tools.creative_dna import CreativeDNA, NarrativeDNA
from bots import writer_bot


class DummyWriter:
    def __init__(self, raw_output: str):
        self.raw_output = raw_output
        self.calls: list[dict] = []

    def write(self, prompt: str, system: str = "") -> str:
        self.calls.append({"prompt": prompt, "system": system})
        return self.raw_output


RAW_OUTPUT = """---TITLE---
Test Title

---META---
Test meta description

---SLUG---
test-slug

---TAGS---
AI, Test
---CORNER---
Easy World

---BODY---
<h2>Body</h2><p>Content</p>

---KEY_POINTS---
- First
- Second

---COUPANG_KEYWORDS---
keyboard
---SOURCES---
https://example.com | Example source | 2026-04-02

---DISCLAIMER---
Be careful
"""


def test_generate_article_supports_style_prefix_without_persisting():
    topic_data = {
        "topic": "AI and the future of humans",
        "corner": "Easy World",
        "description": "Description",
        "source_url": "https://example.com",
        "published_at": "2026-04-02T00:00:00",
    }
    dummy = DummyWriter(RAW_OUTPUT)

    article = writer_bot.generate_article(
        topic_data,
        writer=dummy,
        style_prefix="[Creative DNA]\n",
    )

    assert article["title"] == "Test Title"
    assert article["slug"] == "test-slug"
    assert dummy.calls[0]["system"].startswith("[Creative DNA]\n")


def test_generate_article_accepts_full_narrative_dna_prefix():
    topic_data = {
        "topic": "Why one small object stays with us",
        "corner": "Easy World",
        "description": "Description",
        "source_url": "https://example.com",
        "published_at": "2026-04-02T00:00:00",
    }
    dummy = DummyWriter(RAW_OUTPUT)
    dna = CreativeDNA(
        themes=["wonder", "memory"],
        writing_style_summary="Short and reflective sentences.",
        emotional_register="Quiet but warm.",
        structural_tendency="Begin close and widen toward meaning.",
        philosophical_worldview="Meaning grows through attention to ordinary life.",
        vocabulary_register="Simple words with emotional precision.",
        narrative_dna=NarrativeDNA(
            opening_hook="Start with one ordinary detail.",
            tension_engine="Delay the emotional explanation until the reader leans in.",
            signature_move="Cross realism with allegorical reflection.",
            resolution_pattern="End with a quiet realization.",
        ),
        forbidden_tones=["didactic"],
        key_prop_tendency="One object should carry the emotional turn.",
        sample_sentence="The room changes when one object starts carrying memory.",
    )

    writer_bot.generate_article(
        topic_data,
        writer=dummy,
        style_prefix=dna.to_prompt_context(include_narrative=True),
    )

    assert "Opening hook" in dummy.calls[0]["system"]
    assert "Resolution pattern" in dummy.calls[0]["system"]


def test_write_article_persists_generated_article_with_style_prefix(tmp_path: Path):
    topic_data = {
        "topic": "AI and the future of humans",
        "corner": "Easy World",
        "description": "Description",
        "source_url": "https://example.com",
        "published_at": "2026-04-02T00:00:00",
    }
    dummy = DummyWriter(RAW_OUTPUT)
    output_path = tmp_path / "article.json"

    article = writer_bot.write_article(
        topic_data,
        output_path,
        writer=dummy,
        style_prefix="[Creative DNA]\n",
    )

    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert article["title"] == "Test Title"
    assert saved["title"] == "Test Title"
    assert dummy.calls[0]["system"].startswith("[Creative DNA]\n")
