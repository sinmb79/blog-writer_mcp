from __future__ import annotations

from datetime import datetime, timezone
import importlib
from pathlib import Path
import re
from typing import Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from blogwriter_mcp.tools.creative_dna import CreativeDNAInput, CreativeDNAManager
from blogwriter_mcp.tools.performance_feedback import PerformanceFeedback
from blogwriter_mcp.tools.seo_optimizer import SEOOptimizer, parse_article_html


BASE_DIR = Path(__file__).resolve().parents[1]
(BASE_DIR / "data" / "images").mkdir(parents=True, exist_ok=True)

collector_bot = importlib.import_module("bots.collector_bot")
image_bot = importlib.import_module("bots.image_bot")
linker_bot = importlib.import_module("bots.linker_bot")
publisher_bot = importlib.import_module("bots.publisher_bot")
wp_publisher_bot = importlib.import_module("bots.wp_publisher_bot")
writer_bot = importlib.import_module("bots.writer_bot")


mcp = FastMCP(
    name="blog_writer_mcp",
    instructions=(
        "AI blog automation MCP. It supports trend collection, article writing, SEO optimization, "
        "affiliate link insertion, publishing, performance feedback, and Creative DNA application."
    ),
    host="127.0.0.1",
    port=8766,
    streamable_http_path="/mcp",
)


class TrendingInput(BaseModel):
    category: str | None = None
    region: str = "KR"
    count: int = 10


class WriteArticleInput(BaseModel):
    topic: str
    keywords: list[str] = Field(default_factory=list)
    length: int = 1000
    corner: str = "Easy World"
    description: str = ""
    source_url: str = ""
    published_at: str | None = None
    apply_dna: bool = False
    apply_narrative: bool = True


class ImageInput(BaseModel):
    prompt: str
    topic: str = ""
    style: str = ""


class SEOInput(BaseModel):
    article_html: str
    target_keyword: str
    secondary_keywords: list[str] = Field(default_factory=list)
    title: str = ""


class LinkerInput(BaseModel):
    article_html: str
    title: str = ""
    coupang_keywords: list[str] = Field(default_factory=list)
    max_links: int = 3


class PublishInput(BaseModel):
    title: str
    content: str
    labels: list[str] = Field(default_factory=list)
    scheduled_at: str | None = None
    corner: str = "Easy World"
    meta: str = ""
    slug: str = ""
    sources: list[dict] = Field(default_factory=list)
    quality_score: int = 100
    disclaimer: str = ""
    platform: Literal["blogger", "wordpress", "both"] = "blogger"


class AnalyticsInput(BaseModel):
    days: int = 30
    top_n: int = 5


class PerformanceFeedbackInput(BaseModel):
    days: int = 30
    top_n: int = 5


class PipelineInput(BaseModel):
    topic: str | None = None
    description: str = ""
    category: str | None = None
    region: str = "KR"
    count: int = 5
    corner: str = "Easy World"
    apply_dna: bool = False
    apply_narrative: bool = True
    publish: bool = False


def get_creative_dna_manager() -> CreativeDNAManager:
    return CreativeDNAManager()


def get_performance_feedback_service() -> PerformanceFeedback:
    return PerformanceFeedback()


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or datetime.now().strftime("article-%Y%m%d-%H%M%S")


def _matches_category(item: dict, category: str | None) -> bool:
    if not category:
        return True
    haystack = " ".join(
        [
            item.get("corner", ""),
            item.get("topic_type", ""),
            item.get("source", ""),
            item.get("topic", ""),
        ]
    ).lower()
    return category.lower() in haystack


def _collect_trending_items(params: TrendingInput) -> list[dict]:
    rules = collector_bot.load_config("quality_rules.json")
    sources_cfg = collector_bot.load_config("sources.json")
    published_titles = collector_bot.load_published_titles()
    min_score = rules.get("min_score", 70)

    all_items = []
    all_items.extend(collector_bot.collect_google_trends())
    all_items.extend(collector_bot.collect_github_trending(sources_cfg))
    all_items.extend(collector_bot.collect_product_hunt(sources_cfg))
    all_items.extend(collector_bot.collect_hacker_news(sources_cfg))
    all_items.extend(collector_bot.collect_rss_feeds(sources_cfg))

    passed = []
    for item in all_items:
        if not item.get("topic"):
            continue

        trust_override = item.pop("_trust_override", None)
        if trust_override:
            trust_levels = rules["scoring"]["source_trust"]["levels"]
            item["source_trust_level"] = trust_override
            item["_trust_score"] = trust_levels.get(trust_override, trust_levels["medium"])

        score = collector_bot.calculate_quality_score(item, rules)
        item["quality_score"] = score

        discard_reason = collector_bot.apply_discard_rules(item, rules, published_titles)
        if discard_reason or score < min_score:
            continue

        item["corner"] = item.get("corner") or collector_bot.assign_corner(
            item,
            item.get("topic_type", "trending"),
        )
        item["coupang_keywords"] = item.get("coupang_keywords") or collector_bot.extract_coupang_keywords(
            item.get("topic", ""),
            item.get("description", ""),
        )
        item["region"] = params.region
        item["sources"] = [
            {
                "url": item.get("source_url", ""),
                "title": item.get("topic", ""),
                "date": item.get("published_at", ""),
            }
        ]

        if _matches_category(item, params.category):
            passed.append(item)

    return sorted(passed, key=lambda entry: entry.get("quality_score", 0), reverse=True)[: params.count]


def _pick_target_keyword(topic: dict, article: dict) -> str:
    if article.get("coupang_keywords"):
        return article["coupang_keywords"][0]
    words = re.findall(r"[0-9A-Za-z가-힣]+", topic.get("topic", "") or article.get("title", ""))
    return words[0] if words else article.get("title", "")


def _pick_secondary_keywords(topic: dict, article: dict) -> list[str]:
    secondary = list(article.get("tags", []))
    secondary.extend(topic.get("related_keywords", []))
    deduped = []
    for keyword in secondary:
        if keyword and keyword not in deduped:
            deduped.append(keyword)
    return deduped[:5]


@mcp.tool(name="blog_get_trending")
async def blog_get_trending(params: TrendingInput) -> list[dict]:
    return _collect_trending_items(params)


@mcp.tool(name="blog_write_article")
async def blog_write_article(params: WriteArticleInput) -> dict:
    style_prefix = ""
    manager = get_creative_dna_manager()
    dna = manager.load() if params.apply_dna else None
    if dna:
        style_prefix = dna.to_prompt_context(include_narrative=params.apply_narrative)

    topic_data = {
        "topic": params.topic,
        "corner": params.corner,
        "description": params.description,
        "source_url": params.source_url,
        "published_at": params.published_at or datetime.now(timezone.utc).isoformat(),
    }
    article = writer_bot.generate_article(topic_data, style_prefix=style_prefix)
    if params.keywords:
        article["coupang_keywords"] = params.keywords
    article["dna_applied"] = bool(dna)
    article["narrative_applied"] = bool(dna and params.apply_narrative)
    return article


@mcp.tool(name="blog_generate_image")
async def blog_generate_image(params: ImageInput) -> dict:
    topic = params.topic or params.prompt
    description = " ".join(part for part in [params.style, params.prompt] if part).strip()

    if image_bot.IMAGE_MODE == "auto":
        image_path = image_bot.generate_image_auto(description or topic, topic)
    else:
        image_path = image_bot.process_manual_mode(topic, description=description)

    return {
        "mode": image_bot.IMAGE_MODE,
        "topic": topic,
        "image_path": image_path,
        "prompt": params.prompt,
        "style": params.style,
    }


@mcp.tool(name="blog_optimize_seo")
async def blog_optimize_seo(params: SEOInput) -> dict:
    parsed = parse_article_html(params.article_html)
    if params.title and not parsed.get("title"):
        parsed["title"] = params.title
    return SEOOptimizer().optimize(parsed, params.target_keyword, params.secondary_keywords)


@mcp.tool(name="blog_insert_affiliate_links")
async def blog_insert_affiliate_links(params: LinkerInput) -> dict:
    article = {
        "title": params.title,
        "coupang_keywords": params.coupang_keywords
        or collector_bot.extract_coupang_keywords(params.title, params.article_html),
    }
    content = linker_bot.process(article, params.article_html)
    return {
        "content": content,
        "coupang_keywords": article["coupang_keywords"][: params.max_links],
    }


@mcp.tool(name="blog_publish")
async def blog_publish(params: PublishInput) -> dict:
    article = {
        "title": params.title,
        "meta": params.meta,
        "slug": params.slug or _slugify(params.title),
        "tags": params.labels,
        "corner": params.corner,
        "body": params.content,
        "_html_content": params.content,
        "sources": params.sources,
        "disclaimer": params.disclaimer,
        "quality_score": params.quality_score,
        "scheduled_at": params.scheduled_at,
    }
    publishers = {
        "blogger": publisher_bot.publish,
        "wordpress": wp_publisher_bot.publish,
    }

    selected = ["blogger", "wordpress"] if params.platform == "both" else [params.platform]
    results = {}
    for platform in selected:
        success = publishers[platform](dict(article))
        results[platform] = {
            "published": success,
            "status": "published" if success else "pending_review",
        }

    published = all(entry["published"] for entry in results.values())
    if published:
        status = "published"
    elif any(entry["published"] for entry in results.values()):
        status = "partial_failure"
    else:
        status = "pending_review"

    return {
        "status": status,
        "published": published,
        "scheduled_at": params.scheduled_at,
        "title": params.title,
        "platform": params.platform,
        "results": results,
    }


@mcp.tool(name="blog_get_analytics")
async def blog_get_analytics(params: AnalyticsInput) -> dict:
    return get_performance_feedback_service().get_analytics_summary(days=params.days, top_n=params.top_n)


@mcp.tool(name="blog_set_creative_dna")
async def blog_set_creative_dna(params: CreativeDNAInput) -> dict:
    dna = get_creative_dna_manager().analyze_and_save(params)
    return {
        "status": "saved",
        "extracted_themes": dna.themes,
        "writing_style": dna.writing_style_summary,
        "narrative_dna": dna.narrative_dna.model_dump(),
        "emotional_register": dna.emotional_register,
        "forbidden_tones": dna.forbidden_tones,
        "key_prop_tendency": dna.key_prop_tendency,
        "sample_sentence": dna.sample_sentence,
    }


@mcp.tool(name="blog_get_performance_feedback")
async def blog_get_performance_feedback(params: PerformanceFeedbackInput) -> dict:
    dna = get_creative_dna_manager().load()
    return get_performance_feedback_service().get_feedback(
        days=params.days,
        top_n=params.top_n,
        dna_themes=dna.themes if dna else [],
    )


@mcp.tool(name="blog_full_pipeline")
async def blog_full_pipeline(params: PipelineInput) -> dict:
    if params.topic:
        selected_topic = {
            "topic": params.topic,
            "description": params.description,
            "corner": params.corner,
            "coupang_keywords": collector_bot.extract_coupang_keywords(params.topic, params.description),
        }
    else:
        trending = await blog_get_trending(
            TrendingInput(category=params.category, region=params.region, count=params.count)
        )
        if not trending:
            raise ValueError("No trending topics were available for the requested filters.")
        selected_topic = trending[0]

    article = await blog_write_article(
        WriteArticleInput(
            topic=selected_topic["topic"],
            description=selected_topic.get("description", ""),
            corner=selected_topic.get("corner", params.corner),
            keywords=selected_topic.get("coupang_keywords", []),
            apply_dna=params.apply_dna,
            apply_narrative=params.apply_narrative,
        )
    )

    seo = await blog_optimize_seo(
        SEOInput(
            article_html=article["body"],
            title=article["title"],
            target_keyword=_pick_target_keyword(selected_topic, article),
            secondary_keywords=_pick_secondary_keywords(selected_topic, article),
        )
    )

    linked = await blog_insert_affiliate_links(
        LinkerInput(
            article_html=article["body"],
            title=article["title"],
            coupang_keywords=article.get("coupang_keywords", []),
        )
    )

    image_result = None
    if selected_topic.get("corner") == "시사툰":
        image_result = await blog_generate_image(
            ImageInput(
                topic=article["title"],
                prompt=article.get("meta") or article["title"],
                style="editorial cartoon",
            )
        )

    publish_result = None
    if params.publish:
        publish_result = await blog_publish(
            PublishInput(
                title=article["title"],
                content=linked["content"],
                labels=article.get("tags", []),
                corner=article.get("corner", params.corner),
                meta=article.get("meta", ""),
                slug=article.get("slug", ""),
                sources=article.get("sources", []),
                quality_score=selected_topic.get("quality_score", 100),
                disclaimer=article.get("disclaimer", ""),
            )
        )

    return {
        "selected_topic": selected_topic,
        "article": article,
        "seo": seo,
        "linked_content": linked,
        "image_result": image_result,
        "publish_result": publish_result,
    }


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
