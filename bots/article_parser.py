"""
article_parser.py
OpenClaw blog-writer 출력(output_format.md 형식)을 파싱하여
발행봇이 사용할 수 있는 dict로 변환.
"""
import re
from typing import Optional


def parse_output(raw_output: str) -> Optional[dict]:
    """
    OpenClaw 출력 문자열을 파싱.
    Returns: dict 또는 None (파싱 실패 시)
    """
    sections = {}
    pattern = re.compile(r'---(\w+)---\n(.*?)(?=---\w+---|$)', re.DOTALL)
    matches = pattern.findall(raw_output)

    for key, value in matches:
        sections[key.strip()] = value.strip()

    if not sections.get('TITLE') or not sections.get('BODY'):
        return None

    # 출처 파싱
    sources = []
    sources_raw = sections.get('SOURCES', '')
    for line in sources_raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split('|')]
        sources.append({
            'url': parts[0] if len(parts) > 0 else '',
            'title': parts[1] if len(parts) > 1 else '',
            'date': parts[2] if len(parts) > 2 else '',
        })

    # 태그 파싱
    tags_raw = sections.get('TAGS', '')
    tags = [t.strip() for t in tags_raw.split(',') if t.strip()]

    # 쿠팡 키워드 파싱
    coupang_raw = sections.get('COUPANG_KEYWORDS', '')
    coupang_keywords = [k.strip() for k in coupang_raw.split(',') if k.strip()]

    # KEY_POINTS 파싱 (변환 엔진용 핵심 3줄)
    key_points_raw = sections.get('KEY_POINTS', '')
    key_points = []
    for line in key_points_raw.splitlines():
        line = line.strip().lstrip('•-*').strip()
        if line:
            key_points.append(line)
    key_points = key_points[:3]  # 최대 3개

    return {
        'title': sections.get('TITLE', ''),
        'meta': sections.get('META', ''),
        'slug': sections.get('SLUG', ''),
        'tags': tags,
        'corner': sections.get('CORNER', ''),
        'body': sections.get('BODY', ''),
        'coupang_keywords': coupang_keywords,
        'key_points': key_points,
        'sources': sources,
        'disclaimer': sections.get('DISCLAIMER', ''),
    }


if __name__ == '__main__':
    sample = """---TITLE---
ChatGPT 처음 쓰는 사람을 위한 완전 가이드

---META---
ChatGPT를 처음 사용하는 분을 위한 단계별 가이드입니다.

---SLUG---
chatgpt-beginners-complete-guide

---TAGS---
ChatGPT, AI, 가이드, 입문

---CORNER---
쉬운세상

---BODY---
## ChatGPT란?

ChatGPT는 OpenAI가 만든 AI 챗봇입니다.

## 어떻게 시작하나요?

1단계: chat.openai.com 접속

## 결론

오늘부터 바로 시작해보세요.

---COUPANG_KEYWORDS---
키보드, 마우스

---SOURCES---
https://openai.com/blog | OpenAI 공식 블로그 | 2026-03-24

---DISCLAIMER---
"""
    result = parse_output(sample)
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))
