import json
from pathlib import Path

from bots.converters import thread_converter


ROOT = Path(__file__).resolve().parents[1]


def test_env_example_mentions_wordpress_credentials():
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "WP_URL=https://your-site.com" in env_example
    assert "WP_USERNAME=your_username" in env_example
    assert "WP_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx" in env_example


def test_platforms_config_includes_wordpress_toggle():
    platforms = json.loads((ROOT / "config" / "platforms.json").read_text(encoding="utf-8"))
    assert platforms["blogger"]["enabled"] is True
    assert platforms["wordpress"]["enabled"] is False
    assert platforms["wordpress"]["url"] == ""


def test_readme_uses_the_4th_path_intro():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "## The 4th Path: ⟨H⊕A⟩ ↦ Ω" in text
    assert "Human (H) and AI (A), not as tools and users" in text
    assert "22B Labs | the4thpath.com" in text
    assert "홍익인간" not in text


def test_thread_converter_uses_the_4th_path_branding():
    tweets = thread_converter.convert(
        {
            "title": "Brand update",
            "slug": "brand-update",
            "corner": "인사이트",
            "tags": ["AI"],
            "key_points": ["One", "Two", "Three"],
        },
        save_file=False,
    )

    joined = "\n".join(tweet["text"] for tweet in tweets)
    assert "The 4th Path" in joined
    assert "the4thpath.com" in joined
