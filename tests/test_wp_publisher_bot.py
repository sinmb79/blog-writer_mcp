import base64
import json
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


class _WordPressMockHandler(BaseHTTPRequestHandler):
    categories: dict[str, int] = {}
    tags: dict[str, int] = {}
    media_payloads: list[dict] = []
    post_payloads: list[dict] = []
    auth_headers: list[str] = []

    def log_message(self, format, *args):  # noqa: A003
        return

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(length) if length else b""

    def do_GET(self):  # noqa: N802
        self.__class__.auth_headers.append(self.headers.get("Authorization", ""))
        if self.path.startswith("/wp-json/wp/v2/categories"):
            name = self.path.split("search=", 1)[-1]
            if name in self.__class__.categories:
                self._json(200, [{"id": self.__class__.categories[name], "name": name}])
            else:
                self._json(200, [])
            return
        if self.path.startswith("/wp-json/wp/v2/tags"):
            name = self.path.split("search=", 1)[-1]
            if name in self.__class__.tags:
                self._json(200, [{"id": self.__class__.tags[name], "name": name}])
            else:
                self._json(200, [])
            return
        self._json(404, {"message": "not found"})

    def do_POST(self):  # noqa: N802
        self.__class__.auth_headers.append(self.headers.get("Authorization", ""))
        if self.path == "/wp-json/wp/v2/categories":
            payload = json.loads(self._read_body().decode("utf-8"))
            category_id = len(self.__class__.categories) + 10
            self.__class__.categories[payload["name"]] = category_id
            self._json(201, {"id": category_id, "name": payload["name"]})
            return
        if self.path == "/wp-json/wp/v2/tags":
            payload = json.loads(self._read_body().decode("utf-8"))
            tag_id = len(self.__class__.tags) + 20
            self.__class__.tags[payload["name"]] = tag_id
            self._json(201, {"id": tag_id, "name": payload["name"]})
            return
        if self.path == "/wp-json/wp/v2/media":
            self.__class__.media_payloads.append(
                {
                    "headers": {
                        "Content-Disposition": self.headers.get("Content-Disposition", ""),
                        "Content-Type": self.headers.get("Content-Type", ""),
                    },
                    "size": len(self._read_body()),
                }
            )
            self._json(201, {"id": 99, "source_url": "https://example.com/media/99"})
            return
        if self.path == "/wp-json/wp/v2/posts":
            payload = json.loads(self._read_body().decode("utf-8"))
            self.__class__.post_payloads.append(payload)
            self._json(201, {"id": 777, "link": "https://example.com/posts/777"})
            return
        self._json(404, {"message": "not found"})


@pytest.fixture
def wordpress_server():
    _WordPressMockHandler.categories = {}
    _WordPressMockHandler.tags = {}
    _WordPressMockHandler.media_payloads = []
    _WordPressMockHandler.post_payloads = []
    _WordPressMockHandler.auth_headers = []

    server = ThreadingHTTPServer(("127.0.0.1", 0), _WordPressMockHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_publish_to_wordpress_supports_scheduling_terms_and_media(monkeypatch, tmp_path: Path, wordpress_server):
    import bots.wp_publisher_bot as wp_publisher_bot

    image_path = tmp_path / "cover.png"
    image_path.write_bytes(b"fake-image-bytes")

    scheduled_at = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

    monkeypatch.setattr(wp_publisher_bot, "WP_URL", wordpress_server)
    monkeypatch.setattr(wp_publisher_bot, "WP_USERNAME", "writer")
    monkeypatch.setattr(wp_publisher_bot, "WP_APP_PASSWORD", "abcd efgh ijkl mnop")
    monkeypatch.setattr(wp_publisher_bot, "send_telegram", lambda *args, **kwargs: None)

    article = {
        "title": "WordPress launch post",
        "meta": "Meta description",
        "slug": "wordpress-launch-post",
        "tags": ["AI", "Automation"],
        "corner": "Insights",
        "body": "markdown body",
        "_html_content": "<h1>WordPress launch post</h1><p>content</p>",
        "sources": [
            {"url": "https://example.com/source-1", "title": "Source 1"},
            {"url": "https://example.com/source-2", "title": "Source 2"},
        ],
        "disclaimer": "",
        "quality_score": 100,
        "scheduled_at": scheduled_at,
        "image_path": str(image_path),
    }

    assert wp_publisher_bot.publish(article) is True

    payload = _WordPressMockHandler.post_payloads[-1]
    auth_header = _WordPressMockHandler.auth_headers[-1]
    expected_auth = "Basic " + base64.b64encode(b"writer:abcd efgh ijkl mnop").decode("ascii")

    assert payload["status"] == "future"
    assert payload["date_gmt"] == scheduled_at
    assert payload["categories"] == [10]
    assert payload["tags"] == [20, 21]
    assert payload["featured_media"] == 99
    assert auth_header == expected_auth
    assert _WordPressMockHandler.media_payloads


def test_publish_to_wordpress_can_save_draft(monkeypatch, wordpress_server):
    import bots.wp_publisher_bot as wp_publisher_bot

    monkeypatch.setattr(wp_publisher_bot, "WP_URL", wordpress_server)
    monkeypatch.setattr(wp_publisher_bot, "WP_USERNAME", "writer")
    monkeypatch.setattr(wp_publisher_bot, "WP_APP_PASSWORD", "abcd efgh ijkl mnop")
    monkeypatch.setattr(wp_publisher_bot, "send_telegram", lambda *args, **kwargs: None)

    article = {
        "title": "Draft post",
        "meta": "Meta description",
        "slug": "draft-post",
        "tags": [],
        "corner": "Insights",
        "body": "markdown body",
        "_html_content": "<h1>Draft post</h1><p>content</p>",
        "sources": [
            {"url": "https://example.com/source-1", "title": "Source 1"},
            {"url": "https://example.com/source-2", "title": "Source 2"},
        ],
        "disclaimer": "",
        "quality_score": 100,
        "status": "draft",
    }

    assert wp_publisher_bot.publish(article) is True
    assert _WordPressMockHandler.post_payloads[-1]["status"] == "draft"
