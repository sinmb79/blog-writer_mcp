import asyncio

from blogwriter_mcp import server
from blogwriter_mcp.tools.creative_dna import CreativeDNA, NarrativeDNA


def test_server_registers_expected_tools():
    expected = {
        "blog_get_trending",
        "blog_write_article",
        "blog_generate_image",
        "blog_optimize_seo",
        "blog_insert_affiliate_links",
        "blog_publish",
        "blog_get_analytics",
        "blog_full_pipeline",
        "blog_set_creative_dna",
        "blog_get_performance_feedback",
    }

    registered = set(server.mcp._tool_manager._tools.keys())
    assert expected.issubset(registered)


def test_blog_write_article_applies_saved_dna_and_narrative(monkeypatch):
    captured = {}

    class DummyManager:
        def load(self):
            return CreativeDNA(
                themes=["wonder", "coexistence"],
                writing_style_summary="Short reflective sentences with emotional restraint.",
                emotional_register="Quiet, curious, humane.",
                structural_tendency="Begin from the ordinary and widen into meaning.",
                philosophical_worldview="Technology should move closer to human dignity.",
                vocabulary_register="Simple vocabulary with clear emotional weight.",
                narrative_dna=NarrativeDNA(
                    opening_hook="Start from a small daily detail.",
                    tension_engine="Keep the reader moving by delaying the true emotional meaning.",
                    signature_move="Cross practical reality with allegorical reflection.",
                    resolution_pattern="End with a quiet realization.",
                ),
                forbidden_tones=["didactic"],
                key_prop_tendency="Use one object to carry emotion.",
                sample_sentence="A tool matters only when it helps a person arrive closer to another person.",
            )

    def fake_generate_article(topic_data, writer=None, style_prefix=""):
        captured["style_prefix"] = style_prefix
        return {
            "title": topic_data["topic"],
            "meta": "Meta",
            "slug": "ai-future",
            "tags": ["AI"],
            "corner": topic_data["corner"],
            "body": "<h2>Body</h2><p>Content</p>",
            "coupang_keywords": ["keyboard"],
            "key_points": ["one"],
            "sources": [],
            "disclaimer": "",
        }

    monkeypatch.setattr(server, "get_creative_dna_manager", lambda: DummyManager())
    monkeypatch.setattr(server.writer_bot, "generate_article", fake_generate_article)

    result = asyncio.run(
        server.blog_write_article(
            server.WriteArticleInput(
                topic="AI and the future of humans",
                apply_dna=True,
                apply_narrative=True,
            )
        )
    )

    assert result["dna_applied"] is True
    assert result["narrative_applied"] is True
    assert "Opening hook" in captured["style_prefix"]
    assert "Resolution pattern" in captured["style_prefix"]


def test_blog_write_article_can_disable_narrative_even_when_dna_is_loaded(monkeypatch):
    captured = {}

    class DummyManager:
        def load(self):
            return CreativeDNA(
                themes=["wonder"],
                writing_style_summary="Warm and restrained.",
                emotional_register="Soft curiosity.",
                structural_tendency="Begin close, end wide.",
                philosophical_worldview="Meaning grows through attention.",
                vocabulary_register="Simple and direct words.",
                narrative_dna=NarrativeDNA(
                    opening_hook="Start with a concrete daily image.",
                    tension_engine="Delay interpretation.",
                    signature_move="Pair realism with fable.",
                    resolution_pattern="Close with a calm insight.",
                ),
                forbidden_tones=["cynical"],
                key_prop_tendency="One object anchors the emotional turn.",
                sample_sentence="The room changes when one quiet object starts carrying memory.",
            )

    def fake_generate_article(topic_data, writer=None, style_prefix=""):
        captured["style_prefix"] = style_prefix
        return {
            "title": topic_data["topic"],
            "meta": "Meta",
            "slug": "quiet-object",
            "tags": ["essay"],
            "corner": topic_data["corner"],
            "body": "<h2>Body</h2><p>Content</p>",
            "coupang_keywords": [],
            "key_points": [],
            "sources": [],
            "disclaimer": "",
        }

    monkeypatch.setattr(server, "get_creative_dna_manager", lambda: DummyManager())
    monkeypatch.setattr(server.writer_bot, "generate_article", fake_generate_article)

    result = asyncio.run(
        server.blog_write_article(
            server.WriteArticleInput(
                topic="Why one object stays in memory",
                apply_dna=True,
                apply_narrative=False,
            )
        )
    )

    assert result["dna_applied"] is True
    assert result["narrative_applied"] is False
    assert "Opening hook" not in captured["style_prefix"]
    assert "Writing style" in captured["style_prefix"]


def test_blog_get_analytics_returns_feedback_summary(monkeypatch):
    class DummyFeedback:
        def get_analytics_summary(self, days=30, top_n=10, published_records=None, search_console_rows=None):
            return {"days": days, "post_count": 2, "top_posts": [{"title": "AI Future Strategy"}]}

    monkeypatch.setattr(server, "get_performance_feedback_service", lambda: DummyFeedback())

    result = asyncio.run(server.blog_get_analytics(server.AnalyticsInput(days=14, top_n=3)))

    assert result["days"] == 14
    assert result["top_posts"][0]["title"] == "AI Future Strategy"


def test_blog_full_pipeline_orchestrates_without_publish(monkeypatch):
    async def fake_get_trending(params):
        return [
            {
                "topic": "AI Future Strategy",
                "description": "Description",
                "corner": "Easy World",
                "coupang_keywords": ["keyboard"],
            }
        ]

    async def fake_write_article(params):
        return {
            "title": params.topic,
            "meta": "Meta",
            "slug": "ai-future",
            "tags": ["AI"],
            "corner": params.corner,
            "body": "<h2>Body</h2><p>AI Future Strategy</p>",
            "coupang_keywords": ["keyboard"],
            "sources": [],
            "disclaimer": "",
            "dna_applied": params.apply_dna,
            "narrative_applied": getattr(params, "apply_narrative", False),
        }

    async def fake_optimize_seo(params):
        return {"seo_score": 88, "meta_title": "AI Future Strategy"}

    async def fake_insert_links(params):
        return {"content": params.article_html + "<div>Links</div>"}

    monkeypatch.setattr(server, "blog_get_trending", fake_get_trending)
    monkeypatch.setattr(server, "blog_write_article", fake_write_article)
    monkeypatch.setattr(server, "blog_optimize_seo", fake_optimize_seo)
    monkeypatch.setattr(server, "blog_insert_affiliate_links", fake_insert_links)

    result = asyncio.run(server.blog_full_pipeline(server.PipelineInput(publish=False)))

    assert result["selected_topic"]["topic"] == "AI Future Strategy"
    assert result["seo"]["seo_score"] == 88
    assert result["publish_result"] is None
