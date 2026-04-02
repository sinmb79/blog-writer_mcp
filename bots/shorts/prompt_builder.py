"""
bots/shorts/prompt_builder.py
역할: Sora 2 / AI 영상 프롬프트 공통 빌더

검증된 서식:
  Image Reference → Scene Overview → Characters → Action Flow → Dialogue → Audio

사용:
  from shorts.prompt_builder import build_sora_prompt, llm_sora_prompt
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ─── 구조화 빌더 ──────────────────────────────────────────────────────────────

def build_sora_prompt(
    scene_overview: str,
    characters: str,
    action_flow: list[str],
    dialogue: Optional[list[str]] = None,
    audio: Optional[str] = None,
    image_reference: Optional[str] = None,
    duration: int = 15,
) -> str:
    """
    Sora 2 영상 프롬프트를 검증된 서식으로 조립합니다.

    Args:
        scene_overview:  "[공간] 묘사. [분위기1], [분위기2], [장르] atmosphere."
        characters:      외형/복장/빛 묘사 (영어)
        action_flow:     단계별 장면 흐름 (영어 문장 리스트)
        dialogue:        대화 라인 리스트 (예: ["캐릭터: '대사'", ...])  None이면 생략
        audio:           배경음 설명 (영어)  None이면 생략
        image_reference: 참조 이미지 지시문  None이면 생략
        duration:        영상 길이(초), 기본 15

    Returns:
        완성된 프롬프트 문자열
    """
    parts = []

    if image_reference:
        parts.append(f"Image Reference: {image_reference}")

    parts.append(
        f"Scene Overview: {duration}-second cinematic shot {scene_overview}"
    )

    if characters:
        parts.append(f"Characters: {characters}")

    flow_lines = "\n".join(f"- {step}" if not step.startswith("-") else step
                           for step in action_flow)
    parts.append(f"Action Flow:\n{flow_lines}")

    if dialogue:
        dlg_lines = "\n".join(dialogue)
        parts.append(f"Dialogue:\n{dlg_lines}")

    if audio:
        parts.append(f"Audio: {audio}")

    return "\n\n".join(parts)


# ─── LLM 기반 프롬프트 생성 ───────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a professional Sora 2 / AI video prompt engineer.
You write structured cinematic prompts in the following exact format:

Scene Overview: [N]-second cinematic shot [location/space]. [mood1], [mood2], and [genre] atmosphere.
Characters: [visual description — clothing, glow, color, distinctive features].
Action Flow:
- [step 1: initial state + environment]
[step 2: camera or light movement]
[step 3: camera/subject change — zoom, pan, etc.]
[step 4: climax — light/particle peak]
[step 5: ending — fade out, etc.]
Dialogue:
[Character]: "[line]"
Audio: [ambient sound], [effect sound], [voice tone/gender].

Rules:
- Action Flow, Characters, Audio must be in English.
- Dialogue can be in Korean.
- Be specific about camera movements (slow zoom out/in, dolly, pan).
- Include particle/light behavior (gather, flow, radiate, swirl, shimmer).
- Add "Smooth fade out" or similar ending.
- Output the prompt ONLY, no explanations."""


def llm_sora_prompt(
    scene_text: str,
    genre: str,
    atmosphere: str,
    writer,
    duration: int = 15,
    has_dialogue: bool = True,
    image_reference: Optional[str] = None,
) -> str:
    """
    LLM을 사용해 장면 묘사 → Sora 2 구조화 프롬프트 생성.

    Args:
        scene_text:      한국어 또는 영어 장면 묘사
        genre:           장르 (sci-fi, thriller, fantasy, etc.)
        atmosphere:      분위기 키워드
        writer:          LLM writer 객체 (write(prompt, system) 메서드 지원)
        duration:        영상 길이(초)
        has_dialogue:    대사 섹션 포함 여부
        image_reference: 참조 이미지 지시문

    Returns:
        Sora 2 구조화 프롬프트 문자열
    """
    ref_line = (
        f"\nImage Reference: {image_reference}\n" if image_reference else ""
    )
    dlg_instruction = (
        "Include a Dialogue section with 2-3 Korean lines."
        if has_dialogue else
        "Do NOT include a Dialogue section."
    )

    user_prompt = f"""Convert the following scene description into a Sora 2 structured video prompt.
{ref_line}
Genre: {genre}
Atmosphere: {atmosphere}
Duration: {duration} seconds
Scene: {scene_text}

{dlg_instruction}
Output the structured prompt only:"""

    try:
        result = writer.write(user_prompt, system=_SYSTEM_PROMPT)
        prompt = result.strip()
        # 참조 이미지 지시문이 있는데 LLM이 누락했으면 앞에 삽입
        if image_reference and "Image Reference:" not in prompt:
            prompt = f"Image Reference: {image_reference}\n\n{prompt}"
        return prompt
    except Exception as e:
        logger.error(f"Sora 프롬프트 LLM 생성 실패: {e}")
        return _fallback_sora_prompt(scene_text, genre, atmosphere, duration, image_reference)


def llm_sora_prompt_from_article(
    title: str,
    body: str,
    writer,
    duration: int = 15,
) -> str:
    """
    블로그 포스트 제목/본문 → Sora 2 구조화 프롬프트 생성.

    Args:
        title:    블로그 포스트 제목
        body:     본문 요약 또는 전체 (2000자 이내 권장)
        writer:   LLM writer 객체
        duration: 영상 길이(초)

    Returns:
        Sora 2 구조화 프롬프트 문자열
    """
    user_prompt = f"""Create a Sora 2 structured video prompt for this blog post.

Title: {title}
Body (excerpt): {body[:1500]}

Duration: {duration} seconds
The video should visually represent the blog topic in a cinematic and engaging way.
Dialogue should be in Korean (2-3 lines summarizing the key message).
Output the structured prompt only:"""

    try:
        result = writer.write(user_prompt, system=_SYSTEM_PROMPT)
        return result.strip()
    except Exception as e:
        logger.error(f"블로그 Sora 프롬프트 생성 실패: {e}")
        return _fallback_sora_prompt(
            title, 'cinematic', 'informative, modern', duration
        )


# ─── 폴백 ─────────────────────────────────────────────────────────────────────

def _fallback_sora_prompt(
    scene_text: str,
    genre: str,
    atmosphere: str,
    duration: int = 15,
    image_reference: Optional[str] = None,
) -> str:
    """LLM 실패 시 규칙 기반 프롬프트 생성."""
    ref_line = (
        f"Image Reference: {image_reference}\n\n"
        if image_reference else ""
    )
    return (
        f"{ref_line}"
        f"Scene Overview: {duration}-second cinematic shot in a dramatic space. "
        f"{atmosphere}, {genre} atmosphere.\n\n"
        f"Characters: A central figure illuminated by dramatic light.\n\n"
        f"Action Flow:\n"
        f"- {scene_text[:120]}.\n"
        f"Camera slowly pushes in. Ambient particles gather around the figure.\n"
        f"The light intensifies. Camera pulls back to reveal the full environment.\n"
        f"Light radiates outward at maximum brightness.\n"
        f"Smooth fade out to black.\n\n"
        f"Audio: Cinematic ambient drone, subtle particle shimmer, calm narrative voice."
    )
