import json
from pathlib import Path

from bots import writer_bot


class DummyWriter:
    def __init__(self, raw_output: str):
        self.raw_output = raw_output
        self.calls: list[dict] = []

    def write(self, prompt: str, system: str = "") -> str:
        self.calls.append({"prompt": prompt, "system": system})
        return self.raw_output


RAW_OUTPUT = """---TITLE---
테스트 제목

---META---
테스트 메타 설명

---SLUG---
test-slug

---TAGS---
AI, 테스트

---CORNER---
쉬운세상

---BODY---
<h2>본문</h2><p>내용</p>

---KEY_POINTS---
- 첫째
- 둘째

---COUPANG_KEYWORDS---
키보드

---SOURCES---
https://example.com | 예시 출처 | 2026-04-02

---DISCLAIMER---
주의
"""


def test_generate_article_supports_style_prefix_without_persisting():
    topic_data = {
        "topic": "AI와 인간의 미래",
        "corner": "쉬운세상",
        "description": "설명",
        "source_url": "https://example.com",
        "published_at": "2026-04-02T00:00:00",
    }
    dummy = DummyWriter(RAW_OUTPUT)

    article = writer_bot.generate_article(
        topic_data,
        writer=dummy,
        style_prefix="[창작 DNA]\n",
    )

    assert article["title"] == "테스트 제목"
    assert article["slug"] == "test-slug"
    assert dummy.calls[0]["system"].startswith("[창작 DNA]\n")


def test_write_article_persists_generated_article_with_style_prefix(tmp_path: Path):
    topic_data = {
        "topic": "AI와 인간의 미래",
        "corner": "쉬운세상",
        "description": "설명",
        "source_url": "https://example.com",
        "published_at": "2026-04-02T00:00:00",
    }
    dummy = DummyWriter(RAW_OUTPUT)
    output_path = tmp_path / "article.json"

    article = writer_bot.write_article(
        topic_data,
        output_path,
        writer=dummy,
        style_prefix="[창작 DNA]\n",
    )

    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert article["title"] == "테스트 제목"
    assert saved["title"] == "테스트 제목"
    assert dummy.calls[0]["system"].startswith("[창작 DNA]\n")
