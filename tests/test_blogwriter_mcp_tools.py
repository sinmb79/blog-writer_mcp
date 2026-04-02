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
            "themes": ["freedom", "cosmic connection"],
            "writing_style_summary": "Short sentences that open into reflective meaning.",
            "emotional_register": "Reflective but warm.",
            "structural_tendency": "Begin small, then widen.",
            "philosophical_worldview": "Humanity and technology should coexist with care.",
            "vocabulary_register": "Simple words with quiet depth.",
            "narrative_dna": {
                "opening_hook": "Start from an ordinary scene and widen into a larger question.",
                "tension_engine": "Reveal meaning one layer at a time so the reader keeps moving.",
                "signature_move": "Cross everyday reality with allegorical reflection.",
                "resolution_pattern": "Close with a quiet insight instead of a loud conclusion.",
            },
            "forbidden_tones": ["didactic", "cynical"],
            "key_prop_tendency": "Express emotion through one concrete object.",
            "sample_sentence": "Technology exists to help human connection move closer together.",
        }
    )
    prefs = CreativeDNAInput(
        favorite_authors=["Paulo Coelho"],
        favorite_books=["The Alchemist"],
        favorite_films=["Interstellar"],
        personal_keywords=["technology", "empathy"],
    )

    dna = manager.analyze_and_save(prefs, writer=writer)
    loaded = manager.load()

    assert dna.themes == ["freedom", "cosmic connection"]
    assert loaded.sample_sentence == "Technology exists to help human connection move closer together."
    assert loaded.narrative_dna.opening_hook.startswith("Start from an ordinary scene")
    assert loaded.key_prop_tendency == "Express emotion through one concrete object."
    assert "[Creative DNA Applied]" in loaded.to_prompt_context(include_narrative=True)
    assert "opening hook" not in loaded.to_prompt_context(include_narrative=False).lower()
    assert writer.calls


def test_seo_optimizer_returns_keyword_and_geo_summary():
    html = """
    <h1>AI and the Future of Work</h1>
    <p>AI and the future of work are forcing us to rethink responsibility and collaboration.</p>
    <h2>How AI and Humans Can Work Together</h2>
    <p>AI reduces repetitive tasks while humans keep judgment and empathy in the loop.</p>
    <h2>Conclusion</h2>
    <p>For the future of work with AI, transparent sources and practical strategies matter.</p>
    """

    parsed = parse_article_html(html)
    result = SEOOptimizer().optimize(parsed, "AI", ["humans", "future"])

    assert "AI" in result["meta_title"]
    assert result["headings_check"]["target_keyword_in_headings"] is True
    assert result["keyword_density"]["target_keyword_count"] >= 2
    assert result["geo_optimization"]["answer_blocks"]


def test_performance_feedback_summarizes_topics_times_and_dna_alignment():
    now = datetime(2026, 4, 2, tzinfo=timezone.utc)
    published_records = [
        {
            "title": "AI Future Strategy",
            "corner": "Easy World",
            "tags": ["AI", "future"],
            "published_at": (now - timedelta(days=2)).isoformat(),
            "url": "https://example.com/ai-future",
            "quality_score": 88,
        },
        {
            "title": "Automation Tools Guide",
            "corner": "Tool Security",
            "tags": ["automation", "tools"],
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
        dna_themes=["AI", "future", "coexistence"],
    )

    assert feedback["top_performing_topics"][0]["title"] == "AI Future Strategy"
    assert feedback["best_publish_times"]
    assert feedback["recommended_next_topics"]
    assert feedback["dna_alignment_score"]["matched_posts"] == 1
