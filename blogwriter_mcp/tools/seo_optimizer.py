from __future__ import annotations

import re

from bs4 import BeautifulSoup


def parse_article_html(article_html: str) -> dict:
    soup = BeautifulSoup(article_html, "lxml")
    title = ""
    if soup.find("h1"):
        title = soup.find("h1").get_text(" ", strip=True)
    elif soup.title:
        title = soup.title.get_text(" ", strip=True)

    paragraphs = [node.get_text(" ", strip=True) for node in soup.find_all(["p", "li"])]
    headings = [node.get_text(" ", strip=True) for node in soup.find_all(["h1", "h2", "h3"])]
    content = " ".join([text for text in paragraphs if text]).strip()
    summary = content[:157] + "..." if len(content) > 160 else content
    links = [link.get("href", "") for link in soup.find_all("a", href=True)]

    return {
        "title": title,
        "summary": summary,
        "headings": headings,
        "content": content,
        "links": links,
        "word_count": len(_tokenize(content)),
    }


class SEOOptimizer:
    def optimize(self, parsed: dict, target_keyword: str, secondary_keywords: list[str]) -> dict:
        secondary_keywords = secondary_keywords or []
        keyword_density = self._calc_density(parsed["content"], target_keyword)
        headings_check = self._check_headings(parsed["headings"], target_keyword, secondary_keywords)
        geo = {
            "answer_blocks": self._extract_answer_blocks(parsed["content"], target_keyword),
            "citation_readiness": self._check_citation_readiness(parsed["links"]),
            "structured_data": self._gen_schema_markup(parsed),
        }
        readability = self._calc_readability(parsed["content"])
        suggestions = self._build_suggestions(headings_check, keyword_density, geo, readability)

        return {
            "meta_title": self._gen_meta_title(parsed["title"], target_keyword),
            "meta_description": self._gen_meta_description(parsed["summary"], target_keyword),
            "headings_check": headings_check,
            "internal_links_needed": self._suggest_internal_links(parsed["content"]),
            "keyword_density": keyword_density,
            "readability_score": readability,
            "geo_optimization": geo,
            "seo_score": self._score(keyword_density, headings_check, readability, geo),
            "suggestions": suggestions,
        }

    def _gen_meta_title(self, title: str, target_keyword: str) -> str:
        if target_keyword and target_keyword.lower() not in title.lower():
            return f"{target_keyword} | {title}".strip(" |")
        return title[:60]

    def _gen_meta_description(self, summary: str, target_keyword: str) -> str:
        description = summary or f"{target_keyword}에 관한 핵심 내용을 정리했습니다."
        if target_keyword and target_keyword.lower() not in description.lower():
            description = f"{target_keyword} - {description}"
        return description[:160]

    def _check_headings(self, headings: list[str], target_keyword: str, secondary_keywords: list[str]) -> dict:
        joined = " ".join(headings).lower()
        return {
            "target_keyword_in_headings": target_keyword.lower() in joined if target_keyword else False,
            "missing_secondary_keywords": [
                keyword for keyword in secondary_keywords if keyword.lower() not in joined
            ],
            "heading_count": len(headings),
        }

    def _suggest_internal_links(self, content: str) -> list[str]:
        suggestions = []
        lowered = content.lower()
        if "가이드" in lowered:
            suggestions.append("기초 가이드 문서로 내부 링크 연결")
        if "비교" in lowered:
            suggestions.append("비교/추천 글과 교차 링크 연결")
        if not suggestions:
            suggestions.append("연관 카테고리 글 2개 이상 내부 링크 권장")
        return suggestions

    def _calc_density(self, content: str, target_keyword: str) -> dict:
        words = _tokenize(content)
        pattern = re.escape(target_keyword)
        target_count = len(re.findall(pattern, content, flags=re.IGNORECASE)) if target_keyword else 0
        density = round((target_count / max(len(words), 1)) * 100, 2)
        return {
            "target_keyword": target_keyword,
            "target_keyword_count": target_count,
            "total_words": len(words),
            "density_percent": density,
        }

    def _calc_readability(self, content: str) -> dict:
        sentences = [chunk.strip() for chunk in re.split(r"[.!?]\s+|\n+", content) if chunk.strip()]
        words = _tokenize(content)
        avg_sentence = round(len(words) / max(len(sentences), 1), 2)
        score = max(0, min(100, int(100 - max(avg_sentence - 18, 0) * 3)))
        return {
            "score": score,
            "sentence_count": len(sentences),
            "avg_words_per_sentence": avg_sentence,
        }

    def _extract_answer_blocks(self, content: str, target_keyword: str) -> list[str]:
        sentences = [chunk.strip() for chunk in re.split(r"(?<=[.!?])\s+", content) if chunk.strip()]
        matching = [sentence for sentence in sentences if target_keyword.lower() in sentence.lower()]
        if matching:
            return matching[:3]
        return sentences[:2]

    def _check_citation_readiness(self, links: list[str]) -> dict:
        return {
            "link_count": len(links),
            "has_external_citations": any(link.startswith("http") for link in links),
            "status": "ready" if any(link.startswith("http") for link in links) else "needs_sources",
        }

    def _gen_schema_markup(self, parsed: dict) -> dict:
        return {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": parsed["title"],
            "description": parsed["summary"],
        }

    def _build_suggestions(self, headings: dict, density: dict, geo: dict, readability: dict) -> list[str]:
        suggestions = []
        if not headings["target_keyword_in_headings"]:
            suggestions.append("주요 키워드를 H2 또는 H3 제목에 1회 이상 포함하세요.")
        if density["density_percent"] < 0.5:
            suggestions.append("핵심 키워드가 너무 적습니다. 서론과 결론에 자연스럽게 보강하세요.")
        if geo["citation_readiness"]["status"] != "ready":
            suggestions.append("신뢰 가능한 외부 출처 링크를 추가하세요.")
        if readability["score"] < 70:
            suggestions.append("문장을 더 짧게 나누어 가독성을 높이세요.")
        return suggestions

    def _score(self, density: dict, headings: dict, readability: dict, geo: dict) -> int:
        score = 50
        if headings["target_keyword_in_headings"]:
            score += 15
        if density["density_percent"] >= 0.5:
            score += 10
        if geo["citation_readiness"]["status"] == "ready":
            score += 15
        score += min(readability["score"] // 10, 10)
        return min(score, 100)


def _tokenize(content: str) -> list[str]:
    return re.findall(r"[0-9A-Za-z가-힣]+", content)
