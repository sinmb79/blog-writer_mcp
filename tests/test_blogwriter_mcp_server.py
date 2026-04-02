import asyncio

from blogwriter_mcp import server
from blogwriter_mcp.tools.creative_dna import CreativeDNA


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


def test_blog_write_article_applies_saved_dna(monkeypatch):
    captured = {}

    class DummyManager:
        def load(self):
            return CreativeDNA(
                themes=["우주적 연결"],
                writing_style_summary="간결하고 사색적이다.",
                emotional_register="사색적",
                structural_tendency="짧은 문장 선호",
                philosophical_worldview="인간 존엄",
                vocabulary_register="쉬운 단어로 깊은 의미",
                forbidden_tones=["설교적"],
                sample_sentence="우리는 더 넓은 세계를 상상할 수 있다.",
            )

    def fake_generate_article(topic_data, writer=None, style_prefix=""):
        captured["style_prefix"] = style_prefix
        return {
            "title": topic_data["topic"],
            "meta": "메타",
            "slug": "ai-future",
            "tags": ["AI"],
            "corner": topic_data["corner"],
            "body": "<h2>본문</h2><p>내용</p>",
            "coupang_keywords": ["키보드"],
            "key_points": ["하나"],
            "sources": [],
            "disclaimer": "",
        }

    monkeypatch.setattr(server, "get_creative_dna_manager", lambda: DummyManager())
    monkeypatch.setattr(server.writer_bot, "generate_article", fake_generate_article)

    result = asyncio.run(
        server.blog_write_article(
            server.WriteArticleInput(topic="AI와 인간의 미래", apply_dna=True)
        )
    )

    assert result["dna_applied"] is True
    assert captured["style_prefix"].startswith("[창작 DNA 적용]")


def test_blog_get_analytics_returns_feedback_summary(monkeypatch):
    class DummyFeedback:
        def get_analytics_summary(self, days=30, top_n=10, published_records=None, search_console_rows=None):
            return {"days": days, "post_count": 2, "top_posts": [{"title": "AI 미래 전략"}]}

    monkeypatch.setattr(server, "get_performance_feedback_service", lambda: DummyFeedback())

    result = asyncio.run(server.blog_get_analytics(server.AnalyticsInput(days=14, top_n=3)))

    assert result["days"] == 14
    assert result["top_posts"][0]["title"] == "AI 미래 전략"


def test_blog_full_pipeline_orchestrates_without_publish(monkeypatch):
    async def fake_get_trending(params):
        return [
            {
                "topic": "AI 미래 전략",
                "description": "설명",
                "corner": "쉬운세상",
                "coupang_keywords": ["키보드"],
            }
        ]

    async def fake_write_article(params):
        return {
            "title": params.topic,
            "meta": "메타",
            "slug": "ai-future",
            "tags": ["AI"],
            "corner": params.corner,
            "body": "<h2>본문</h2><p>AI 미래 전략</p>",
            "coupang_keywords": ["키보드"],
            "sources": [],
            "disclaimer": "",
            "dna_applied": params.apply_dna,
        }

    async def fake_optimize_seo(params):
        return {"seo_score": 88, "meta_title": "AI 미래 전략"}

    async def fake_insert_links(params):
        return {"content": params.article_html + "<div>링크</div>"}

    monkeypatch.setattr(server, "blog_get_trending", fake_get_trending)
    monkeypatch.setattr(server, "blog_write_article", fake_write_article)
    monkeypatch.setattr(server, "blog_optimize_seo", fake_optimize_seo)
    monkeypatch.setattr(server, "blog_insert_affiliate_links", fake_insert_links)

    result = asyncio.run(server.blog_full_pipeline(server.PipelineInput(publish=False)))

    assert result["selected_topic"]["topic"] == "AI 미래 전략"
    assert result["seo"]["seo_score"] == 88
    assert result["publish_result"] is None
