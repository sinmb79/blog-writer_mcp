# The 4th Path: ⟨H⊕A⟩ ↦ Ω
# Human × AI → a better world.
# 22B Labs | the4thpath.com
"""
WordPress publisher for blog-writer-mcp.

Publishes posts through the WordPress REST API using Application Password
authentication while keeping the same module-level publish(article) interface
as the Blogger publisher.
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import os
from pathlib import Path
from urllib.parse import quote

import requests
from dotenv import load_dotenv

from bots import publisher_bot

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

BASE_DIR = Path(__file__).parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler(LOG_DIR / "wp_publisher.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.INFO)

WP_URL = os.getenv("WP_URL", "").rstrip("/")
WP_USERNAME = os.getenv("WP_USERNAME", "")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD", "")
send_telegram = publisher_bot.send_telegram


def _auth_header() -> dict[str, str]:
    token = base64.b64encode(f"{WP_USERNAME}:{WP_APP_PASSWORD}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def _request(method: str, path: str, **kwargs) -> requests.Response:
    if not WP_URL:
        raise RuntimeError("WP_URL is not configured.")
    headers = dict(kwargs.pop("headers", {}))
    headers.update(_auth_header())
    response = requests.request(
        method,
        f"{WP_URL}/wp-json/wp/v2/{path}",
        headers=headers,
        timeout=30,
        **kwargs,
    )
    response.raise_for_status()
    return response


def _ensure_credentials() -> bool:
    if not all([WP_URL, WP_USERNAME, WP_APP_PASSWORD]):
        logger.error("WordPress credentials are missing. Set WP_URL, WP_USERNAME, and WP_APP_PASSWORD.")
        return False
    return True


def _normalize_names(values: object) -> list[str]:
    if not values:
        return []
    if isinstance(values, str):
        values = [part.strip() for part in values.split(",")]
    return [str(value).strip() for value in values if str(value).strip()]


def _get_or_create_term(taxonomy: str, name: str) -> int:
    response = _request("GET", f"{taxonomy}?search={quote(name)}")
    existing = response.json()
    if existing:
        return int(existing[0]["id"])

    create_response = _request("POST", taxonomy, json={"name": name})
    return int(create_response.json()["id"])


def _upload_media(image_path: str) -> int:
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image path does not exist: {image_path}")

    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    headers = {
        "Content-Disposition": f'attachment; filename="{path.name}"',
        "Content-Type": content_type,
    }
    response = _request("POST", "media", headers=headers, data=path.read_bytes())
    return int(response.json()["id"])


def _build_post_payload(article: dict, html_content: str) -> dict:
    categories = _normalize_names(article.get("categories")) or _normalize_names([article.get("corner", "")])
    tags = _normalize_names(article.get("tags"))

    payload = {
        "title": article.get("title", ""),
        "slug": article.get("slug", ""),
        "content": html_content,
        "excerpt": article.get("meta", ""),
        "status": "publish",
    }

    if categories:
        payload["categories"] = [_get_or_create_term("categories", name) for name in categories]
    if tags:
        payload["tags"] = [_get_or_create_term("tags", name) for name in tags]

    explicit_status = str(article.get("status", "")).strip().lower()
    scheduled_at = article.get("scheduled_at")
    if explicit_status == "draft":
        payload["status"] = "draft"
    elif scheduled_at:
        payload["status"] = "future"
        payload["date_gmt"] = scheduled_at

    image_path = article.get("featured_image_path") or article.get("image_path")
    if image_path:
        payload["featured_media"] = _upload_media(str(image_path))

    return payload


def publish(article: dict) -> bool:
    logger.info("WordPress publish attempt: %s", article.get("title", ""))

    if not _ensure_credentials():
        return False

    safety_cfg = publisher_bot.load_config("safety_keywords.json")
    needs_review, review_reason = publisher_bot.check_safety(article, safety_cfg)
    if needs_review:
        logger.warning("Pending manual review for WordPress publish: %s", review_reason)
        publisher_bot.save_pending_review(article, review_reason)
        publisher_bot.send_pending_review_alert(article, review_reason)
        return False

    if article.get("_html_content"):
        full_html = article["_html_content"]
    else:
        body_html, toc_html = publisher_bot.markdown_to_html(article.get("body", ""))
        body_html = publisher_bot.insert_adsense_placeholders(body_html)
        full_html = publisher_bot.build_full_html(article, body_html, toc_html)

    try:
        payload = _build_post_payload(article, full_html)
        response = _request("POST", "posts", json=payload)
        result = response.json()
    except Exception as exc:
        logger.error("WordPress publish failed: %s", exc)
        return False

    post_url = result.get("link", "")
    publisher_bot.log_published(
        article,
        {
            "id": result.get("id", ""),
            "url": post_url,
        },
    )
    send_telegram(
        f"??<b>WordPress published</b>\n\n"
        f"?뱦 <b>{article.get('title', '')}</b>\n"
        f"URL: {post_url}"
    )
    logger.info("WordPress publish complete: %s", post_url)
    return True


__all__ = ["publish"]
