"""
bots/shorts/hook_optimizer.py
Hook text quality scoring and optimization.

HookOptimizer:
  - score(hook): 0-100 quality score based on pattern match + keyword strength
  - optimize(hook, article, max_attempts): regenerate if score < 70

V3.0 scope: pattern matching + LLM regeneration via existing writer_bot
"""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Hook patterns mapped to template strings with {N} placeholder for numbers
HOOK_PATTERNS = {
    'disbelief': [
        '이거 모르면 손해',
        '이게 무료라고?',
        '이걸 아직도 모른다고?',
        '믿기 힘들지만 사실입니다',
        '실화입니다',
    ],
    'warning': [
        '절대 하지 마세요',
        '이것만은 피하세요',
        '지금 당장 멈추세요',
        '알면 충격받을 수 있습니다',
    ],
    'number': [
        '단 {N}초면',
        '{N}%가 모르는',
        '{N}가지 방법',
        '{N}배 빠른',
        '상위 {N}%',
    ],
    'question': [
        '왜 아무도 안 알려줄까?',
        '진짜일까?',
        '이게 가능한 이유',
        '어떻게 하는 걸까?',
    ],
    'urgency': [
        '지금 당장',
        '오늘 안에',
        '지금 안 보면 후회',
        '당장 시작해야 하는 이유',
    ],
}

# High-value keywords that boost score (Korean viral hook words)
HIGH_VALUE_KEYWORDS = [
    '무료', '공짜', '비밀', '충격', '실화', '진짜', '불법',
    '모르는', '숨겨진', '알려지지 않은', '믿기지 않는', '손해',
    '당장', '지금', '반드시', '절대', '꼭', '필수',
    '돈', '수익', '수입', '부자', '성공', '자유',
    '초보', '누구나', '쉬운', '간단한',
]

# Weak words that reduce score
WEAK_KEYWORDS = [
    '알아보겠습니다', '살펴보겠습니다', '설명드리겠습니다',
    '안녕하세요', '오늘은', '이번에는', '먼저',
]


class HookOptimizer:
    """
    Scores and optimizes hook text for shorts videos.

    Score = pattern_score (0-50) + keyword_score (0-30) + length_score (0-20)
    Threshold: 70 — below this triggers regeneration
    """

    def __init__(self, threshold: int = 70):
        self.threshold = threshold
        self._recently_used_patterns: list[str] = []  # avoid repetition

    def score(self, hook: str) -> int:
        """
        Score a hook text from 0-100.

        Components:
        - pattern_score (0-50): does it match a known viral pattern?
        - keyword_score (0-30): does it contain high-value keywords?
        - length_score (0-20): optimal length (15-30 chars = max)
        """
        if not hook:
            return 0

        pattern_score = self._score_pattern(hook)
        keyword_score = self._score_keywords(hook)
        length_score = self._score_length(hook)

        total = min(100, pattern_score + keyword_score + length_score)
        return total

    def optimize(
        self,
        hook: str,
        article: dict,
        max_attempts: int = 3,
        llm_fn=None,
    ) -> str:
        """
        Score hook. If score < threshold, regenerate up to max_attempts times.

        Args:
            hook: Initial hook text
            article: Article dict with keys: title, body, corner, key_points
            max_attempts: Max regeneration attempts
            llm_fn: Optional callable(prompt) -> str for LLM regeneration.
                    If None, returns original hook (LLM not available).

        Returns: Best hook found (may still be below threshold if all attempts fail)
        """
        current = hook
        best = hook
        best_score = self.score(hook)

        logger.info(f'[훅] 초기 점수: {best_score}/100 — "{hook[:30]}..."')

        if best_score >= self.threshold:
            return hook

        if llm_fn is None:
            logger.warning(f'[훅] 점수 부족 ({best_score}/100) — LLM 없음, 원본 사용')
            return hook

        for attempt in range(max_attempts):
            prompt = self._build_regeneration_prompt(current, article, best_score)

            try:
                new_hook = llm_fn(prompt)
                if new_hook:
                    new_hook = new_hook.strip().split('\n')[0]  # Take first line
                    new_score = self.score(new_hook)
                    logger.info(f'[훅] 시도 {attempt+1}: {new_score}/100 — "{new_hook[:30]}"')

                    if new_score > best_score:
                        best = new_hook
                        best_score = new_score

                    if best_score >= self.threshold:
                        break

                    current = new_hook
            except Exception as e:
                logger.warning(f'[훅] LLM 재생성 실패 (시도 {attempt+1}): {e}')
                break

        logger.info(f'[훅] 최종 점수: {best_score}/100 — "{best[:30]}"')
        return best

    def _score_pattern(self, hook: str) -> int:
        """Check if hook matches known viral patterns. Max 50 points."""
        for pattern_name, templates in HOOK_PATTERNS.items():
            for template in templates:
                # Check for fuzzy match (template with {N} filled in)
                pattern_re = re.escape(template).replace(r'\{N\}', r'\d+')
                if re.search(pattern_re, hook):
                    # Recently used pattern gets reduced score
                    if pattern_name in self._recently_used_patterns[-3:]:
                        return 30
                    self._recently_used_patterns.append(pattern_name)
                    return 50
                # Partial match check
                core = template.replace('{N}', '').strip()
                if len(core) > 3 and core in hook:
                    return 35
        return 0

    def _score_keywords(self, hook: str) -> int:
        """Score based on high-value/weak keywords. Max 30 points."""
        score = 0
        for kw in HIGH_VALUE_KEYWORDS:
            if kw in hook:
                score += 10
                if score >= 30:
                    break

        # Penalize weak words
        for kw in WEAK_KEYWORDS:
            if kw in hook:
                score -= 15

        return max(0, min(30, score))

    def _score_length(self, hook: str) -> int:
        """Score based on hook length. Max 20 points. Optimal: 15-30 chars."""
        length = len(hook)
        if 15 <= length <= 30:
            return 20
        elif 10 <= length < 15 or 30 < length <= 40:
            return 10
        elif length < 10:
            return 5
        else:  # > 40 chars
            return 0

    def _build_regeneration_prompt(self, hook: str, article: dict, current_score: int) -> str:
        """Build LLM prompt for hook regeneration."""
        title = article.get('title', '')
        corner = article.get('corner', '')
        key_points = article.get('key_points', [])
        recently_used = ', '.join(self._recently_used_patterns[-3:]) if self._recently_used_patterns else '없음'

        points_str = '\n'.join(f'- {p}' for p in key_points[:3]) if key_points else ''

        return f"""다음 쇼츠 영상의 훅 텍스트를 개선해주세요.

현재 훅: {hook}
현재 점수: {current_score}/100 (기준: 70점 이상)

콘텐츠 정보:
- 제목: {title}
- 코너: {corner}
- 핵심 포인트: {points_str}

요구사항:
1. 15-30자 이내
2. 다음 패턴 중 하나 사용: 충격/의심/경고/숫자/긴급
3. 최근 사용된 패턴 제외: {recently_used}
4. 한국어로 작성
5. 훅 텍스트만 출력 (설명 없이)

개선된 훅:"""


# ── Standalone test ──────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    if '--test' in sys.argv:
        optimizer = HookOptimizer()
        test_hooks = [
            '이거 모르면 손해입니다!',
            '안녕하세요 오늘은 AI에 대해 설명드리겠습니다',
            '100%가 모르는 무료 도구',
            '지금 당장 이것만은 절대 하지 마세요',
            '어',
        ]
        print("=== Hook Optimizer Test ===")
        for hook in test_hooks:
            s = optimizer.score(hook)
            print(f'점수 {s:3d}/100: "{hook}"')
        print()
        print("Pattern test:")
        for category in HOOK_PATTERNS:
            print(f"  {category}: {len(HOOK_PATTERNS[category])} patterns")
