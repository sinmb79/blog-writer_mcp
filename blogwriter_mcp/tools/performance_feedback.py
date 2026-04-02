from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from bots import analytics_bot


class PerformanceFeedback:
    def __init__(self, now_factory=None):
        self.now_factory = now_factory or (lambda: datetime.now(timezone.utc))

    def get_feedback(
        self,
        days: int = 30,
        top_n: int = 5,
        published_records: list[dict] | None = None,
        search_console_rows: list[dict] | None = None,
        dna_themes: list[str] | None = None,
    ) -> dict:
        records = self._load_records(days, published_records)
        rows = search_console_rows if search_console_rows is not None else self._load_search_console_rows(days)
        ranked = self._rank_topics(records, rows)
        return {
            "top_performing_topics": ranked[:top_n],
            "best_publish_times": self._best_publish_times(records),
            "keyword_opportunities": self._keyword_opportunities(records, ranked),
            "recommended_next_topics": self._recommend_next_topics(records, ranked, dna_themes or []),
            "dna_alignment_score": self._dna_alignment(records, dna_themes or []),
        }

    def get_analytics_summary(
        self,
        days: int = 30,
        top_n: int = 10,
        published_records: list[dict] | None = None,
        search_console_rows: list[dict] | None = None,
    ) -> dict:
        records = self._load_records(days, published_records)
        rows = search_console_rows if search_console_rows is not None else self._load_search_console_rows(days)
        ranked = self._rank_topics(records, rows)
        total_clicks = sum(item["clicks"] for item in ranked)
        total_impressions = sum(item["impressions"] for item in ranked)
        avg_ctr = round((total_clicks / max(total_impressions, 1)) * 100, 2)
        return {
            "days": days,
            "post_count": len(records),
            "average_ctr": avg_ctr,
            "top_posts": ranked[:top_n],
            "best_publish_times": self._best_publish_times(records),
        }

    def _load_records(self, days: int, published_records: list[dict] | None) -> list[dict]:
        records = published_records if published_records is not None else analytics_bot.load_published_records()
        cutoff = self.now_factory() - timedelta(days=days)
        result = []
        for record in records:
            published_at = self._parse_datetime(record.get("published_at"))
            if published_at and published_at >= cutoff:
                result.append(record)
        return result

    def _load_search_console_rows(self, days: int) -> list[dict]:
        creds = analytics_bot.get_google_credentials()
        site_url = analytics_bot.os.getenv("GOOGLE_SEARCH_CONSOLE_SITE") or analytics_bot.os.getenv("BLOG_SITE_URL", "")
        if not creds or not getattr(creds, "valid", False) or not site_url:
            return []
        end_date = self.now_factory().strftime("%Y-%m-%d")
        start_date = (self.now_factory() - timedelta(days=days)).strftime("%Y-%m-%d")
        return analytics_bot.get_search_console_data(site_url, start_date, end_date, creds).get("rows", [])

    def _rank_topics(self, records: list[dict], rows: list[dict]) -> list[dict]:
        rows_by_url = {row.get("keys", [""])[0]: row for row in rows}
        ranked = []
        for record in records:
            row = rows_by_url.get(record.get("url", ""), {})
            clicks = row.get("clicks", 0)
            impressions = row.get("impressions", 0)
            ctr = round((clicks / max(impressions, 1)) * 100, 2)
            ranked.append(
                {
                    "title": record.get("title", ""),
                    "corner": record.get("corner", ""),
                    "url": record.get("url", ""),
                    "clicks": clicks,
                    "impressions": impressions,
                    "ctr": ctr,
                    "quality_score": record.get("quality_score", 0),
                    "tags": record.get("tags", []),
                }
            )
        return sorted(ranked, key=lambda item: (item["clicks"], item["ctr"], item["quality_score"]), reverse=True)

    def _best_publish_times(self, records: list[dict]) -> list[dict]:
        counter = Counter()
        for record in records:
            published_at = self._parse_datetime(record.get("published_at"))
            if published_at:
                counter[published_at.hour] += 1
        return [
            {"hour": hour, "post_count": count}
            for hour, count in counter.most_common(3)
        ]

    def _keyword_opportunities(self, records: list[dict], ranked: list[dict]) -> list[str]:
        used_tags = Counter()
        for record in records:
            for tag in record.get("tags", []):
                used_tags[tag] += 1

        opportunities = []
        for item in ranked:
            for tag in item.get("tags", []):
                if used_tags[tag] <= 1:
                    opportunities.append(tag)
        if not opportunities:
            opportunities = [item["corner"] for item in ranked[:3] if item.get("corner")]
        return list(dict.fromkeys(opportunities))[:5]

    def _recommend_next_topics(self, records: list[dict], ranked: list[dict], dna_themes: list[str]) -> list[str]:
        corners = Counter(record.get("corner", "기타") for record in records if record.get("corner"))
        leading_corner = corners.most_common(1)[0][0] if corners else "쉬운세상"
        tag_candidates = [tag for item in ranked for tag in item.get("tags", [])]
        combined = list(dict.fromkeys(dna_themes + tag_candidates))
        recommendations = [f"{leading_corner}: {keyword} 확장 글" for keyword in combined[:3]]
        if not recommendations:
            recommendations.append(f"{leading_corner}: 성과 높은 주제 재가공")
        return recommendations

    def _dna_alignment(self, records: list[dict], dna_themes: list[str]) -> dict:
        if not dna_themes:
            return {"matched_posts": 0, "total_posts": len(records), "ratio": 0.0}

        matched = 0
        lowered_themes = [theme.lower() for theme in dna_themes]
        for record in records:
            haystack = " ".join([record.get("title", "")] + record.get("tags", [])).lower()
            if any(theme in haystack for theme in lowered_themes):
                matched += 1

        return {
            "matched_posts": matched,
            "total_posts": len(records),
            "ratio": round(matched / max(len(records), 1), 2),
        }

    @staticmethod
    def _parse_datetime(raw: str | None) -> datetime | None:
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
