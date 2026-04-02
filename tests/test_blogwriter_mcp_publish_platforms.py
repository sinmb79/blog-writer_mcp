import asyncio

from blogwriter_mcp import server


def test_blog_publish_routes_to_wordpress(monkeypatch):
    called = {}

    def fake_publish(article):
        called["article"] = article
        return True

    monkeypatch.setattr(
        server,
        "wp_publisher_bot",
        type("DummyWp", (), {"publish": staticmethod(fake_publish)}),
        raising=False,
    )

    result = asyncio.run(
        server.blog_publish(
            server.PublishInput(
                title="WordPress title",
                content="<p>html</p>",
                labels=["AI"],
                corner="Insights",
                platform="wordpress",
            )
        )
    )

    assert result["platform"] == "wordpress"
    assert result["published"] is True
    assert result["results"]["wordpress"]["published"] is True
    assert called["article"]["title"] == "WordPress title"


def test_blog_publish_routes_to_both(monkeypatch):
    calls = []

    def fake_blogger_publish(article):
        calls.append(("blogger", article["title"]))
        return True

    def fake_wordpress_publish(article):
        calls.append(("wordpress", article["title"]))
        return True

    monkeypatch.setattr(server.publisher_bot, "publish", fake_blogger_publish)
    monkeypatch.setattr(
        server,
        "wp_publisher_bot",
        type("DummyWp", (), {"publish": staticmethod(fake_wordpress_publish)}),
        raising=False,
    )

    result = asyncio.run(
        server.blog_publish(
            server.PublishInput(
                title="Shared title",
                content="<p>html</p>",
                labels=["AI"],
                corner="Insights",
                platform="both",
            )
        )
    )

    assert result["platform"] == "both"
    assert result["published"] is True
    assert result["results"]["blogger"]["published"] is True
    assert result["results"]["wordpress"]["published"] is True
    assert calls == [("blogger", "Shared title"), ("wordpress", "Shared title")]
