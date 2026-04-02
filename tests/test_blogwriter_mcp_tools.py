import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from blogwriter_mcp.tools.creative_dna import CreativeDNAInput, CreativeDNAManager
from blogwriter_mcp.tools.performance_feedback import PerformanceFeedback
from blogwriter_mcp.tools.seo_optimizer import SEOOptimizer, parse_article_html


class DummyWriter:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls: list[dict] = []

    def write(self, prompt: str, system: str = "") -> str:
        self.calls.append({"prompt": prompt, "system": system})
        return json.dumps(self.payload, ensure_ascii=False)


def test_creative_dna_manager_analyze_and_save_round_trips_file(tmp_path: Path):
    manager = CreativeDNAManager(config_path=tmp_path / "creative_dna.json")
    writer = DummyWriter(
        {
            "themes": ["자유", "우주적 연결"],
            "writing_style_summary": "간결한 문장으로 깊은 의미를 전한다.",
            "emotional_register": "사색적",
            "structural_tendency": "짧은 문장 선호",
            "philosophical_worldview": "인간 존엄",
            "vocabulary_register": "쉬운 단어로 깊은 의미",
            "forbidden_tones": ["설교적", "냉소적"],
            "sample_sentence": "우리는 더 넓은 세계를 상상할 수 있다.",
        }
    )
    prefs = CreativeDNAInput(
        favorite_authors=["파울로 코엘료"],
        favorite_books=["연금술사"],
        favorite_films=["인터스텔라"],
        personal_keywords=["홍익인간"],
    )

    dna = manager.analyze_and_save(prefs, writer=writer)
    loaded = manager.load()

    assert dna.themes == ["자유", "우주적 연결"]
    assert loaded.sample_sentence == "우리는 더 넓은 세계를 상상할 수 있다."
    assert "[창작 DNA 적용]" in loaded.to_prompt_context()
    assert writer.calls


def test_seo_optimizer_returns_keyword_and_geo_summary():
    html = """
    <h1>AI와 인간의 미래</h1>
    <p>AI와 인간의 미래는 협업과 책임 있는 설계에 달려 있습니다.</p>
    <h2>AI와 인간이 함께 일하는 방법</h2>
    <p>AI는 반복 업무를 줄이고 인간은 판단과 공감을 맡습니다.</p>
    <h2>결론</h2>
    <p>AI와 인간의 미래를 위해 신뢰 가능한 출처와 실천 전략이 중요합니다.</p>
    """

    parsed = parse_article_html(html)
    result = SEOOptimizer().optimize(parsed, "AI", ["인간", "미래"])

    assert "AI" in result["meta_title"]
    assert result["headings_check"]["target_keyword_in_headings"] is True
    assert result["keyword_density"]["target_keyword_count"] >= 2
    assert result["geo_optimization"]["answer_blocks"]


def test_performance_feedback_summarizes_topics_times_and_dna_alignment():
    now = datetime(2026, 4, 2, tzinfo=timezone.utc)
    published_records = [
        {
            "title": "AI 미래 전략",
            "corner": "쉬운세상",
            "tags": ["AI", "미래"],
            "published_at": (now - timedelta(days=2)).isoformat(),
            "url": "https://example.com/ai-future",
            "quality_score": 88,
        },
        {
            "title": "업무 자동화 도구",
            "corner": "숨은보물",
            "tags": ["자동화", "도구"],
            "published_at": (now - timedelta(days=5)).isoformat(),
            "url": "https://example.com/automation-tools",
            "quality_score": 82,
        },
    ]
    search_console_rows = [
        {"keys": ["https://example.com/ai-future"], "clicks": 12, "impressions": 100},
        {"keys": ["https://example.com/automation-tools"], "clicks": 3, "impressions": 40},
    ]

    feedback = PerformanceFeedback(now_factory=lambda: now).get_feedback(
        days=30,
        top_n=2,
        published_records=published_records,
        search_console_rows=search_console_rows,
        dna_themes=["AI", "미래", "공존"],
    )

    assert feedback["top_performing_topics"][0]["title"] == "AI 미래 전략"
    assert feedback["best_publish_times"]
    assert feedback["recommended_next_topics"]
    assert feedback["dna_alignment_score"]["matched_posts"] == 1
