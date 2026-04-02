"""
이미지봇 (image_bot.py)
역할: 만평 코너용 이미지 생성/관리

IMAGE_MODE 환경변수로 모드 선택:

  manual  (기본) — 한컷 글 발행 시점에 프롬프트 1개를 Telegram으로 전송.
                   사용자가 직접 생성 후 data/images/ 에 파일 저장.

  request        — 스케줄러가 주기적으로 대기 중인 프롬프트 목록을 Telegram 전송.
                   사용자가 생성형 AI로 이미지 제작 후 Telegram으로 이미지 전송하면 자동 저장.
                   /images 명령으로 대기 목록 확인, /imgpick [번호]로 선택.

  auto           — OpenAI Images API (dall-e-3) 직접 호출. OPENAI_API_KEY 필요.
                   비용: 이미지당 $0.04-0.08 (ChatGPT Pro 구독과 별도).
"""
import json
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / '.env')

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / 'data'
IMAGES_DIR = DATA_DIR / 'images'
LOG_DIR = BASE_DIR / 'logs'
PENDING_PROMPTS_FILE = IMAGES_DIR / 'pending_prompts.json'

LOG_DIR.mkdir(exist_ok=True)
IMAGES_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'image_bot.log', encoding='utf-8'),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
IMAGE_MODE = os.getenv('IMAGE_MODE', 'manual').lower()  # manual | request | auto


# ─── Telegram 전송 ────────────────────────────────────

def send_telegram(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram 설정 없음")
        print(text)
        return
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    try:
        requests.post(url, json={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': text,
            'parse_mode': 'HTML',
        }, timeout=10)
    except Exception as e:
        logger.error(f"Telegram 전송 실패: {e}")


# ─── 프롬프트 생성 ────────────────────────────────────

def build_cartoon_prompt(topic: str, description: str = '') -> str:
    """만평 스타일 이미지 프롬프트 생성 (범용 — 어떤 생성형 AI에도 사용 가능)"""
    desc_part = f" {description}" if description else ""
    prompt = (
        f"Korean editorial cartoon style, single panel.{desc_part} "
        f"Topic: {topic}. "
        f"Style: simple line art, expressive characters, thought-provoking social commentary, "
        f"Korean newspaper cartoon aesthetic, minimal color, black and white with accent colors. "
        f"No text in the image. Square format 1:1."
    )
    return prompt


# ─── 대기 프롬프트 관리 ───────────────────────────────

def load_pending_prompts() -> list[dict]:
    """pending_prompts.json 로드"""
    if not PENDING_PROMPTS_FILE.exists():
        return []
    try:
        return json.loads(PENDING_PROMPTS_FILE.read_text(encoding='utf-8'))
    except Exception:
        return []


def save_pending_prompts(prompts: list[dict]):
    """pending_prompts.json 저장"""
    PENDING_PROMPTS_FILE.write_text(
        json.dumps(prompts, ensure_ascii=False, indent=2), encoding='utf-8'
    )


def add_pending_prompt(topic: str, description: str, article_ref: str = '') -> dict:
    """새 프롬프트 대기 목록에 추가. 생성된 항목 반환."""
    prompts = load_pending_prompts()
    # 같은 주제가 이미 있으면 추가하지 않음
    for p in prompts:
        if p['topic'] == topic and p['status'] == 'pending':
            logger.info(f"이미 대기 중인 프롬프트: {topic}")
            return p

    prompt_text = build_cartoon_prompt(topic, description)
    item = {
        'id': str(len(prompts) + 1),  # 사람이 읽기 쉬운 번호
        'uid': uuid.uuid4().hex[:8],
        'topic': topic,
        'description': description,
        'prompt': prompt_text,
        'article_ref': article_ref,
        'status': 'pending',  # pending | selected | done
        'created_at': datetime.now().isoformat(),
        'image_path': '',
    }
    prompts.append(item)
    save_pending_prompts(prompts)
    logger.info(f"프롬프트 추가 #{item['id']}: {topic}")
    return item


def get_pending_prompts(status: str = 'pending') -> list[dict]:
    """상태별 프롬프트 목록"""
    return [p for p in load_pending_prompts() if p['status'] == status]


def mark_prompt_selected(prompt_id: str) -> dict | None:
    """사용자가 선택한 프롬프트를 selected 상태로 변경"""
    prompts = load_pending_prompts()
    for p in prompts:
        if p['id'] == str(prompt_id):
            p['status'] = 'selected'
            p['selected_at'] = datetime.now().isoformat()
            save_pending_prompts(prompts)
            return p
    return None


def mark_prompt_done(prompt_id: str, image_path: str) -> dict | None:
    """이미지 수령 완료 처리"""
    prompts = load_pending_prompts()
    for p in prompts:
        if p['id'] == str(prompt_id):
            p['status'] = 'done'
            p['image_path'] = image_path
            p['done_at'] = datetime.now().isoformat()
            save_pending_prompts(prompts)
            logger.info(f"프롬프트 #{prompt_id} 완료: {image_path}")
            return p
    return None


def get_prompt_by_id(prompt_id: str) -> dict | None:
    for p in load_pending_prompts():
        if p['id'] == str(prompt_id):
            return p
    return None


# ─── 이미지 수신 저장 ─────────────────────────────────

def save_image_from_bytes(image_bytes: bytes, topic: str, prompt_id: str) -> str:
    """bytes로 받은 이미지를 data/images/ 에 저장. 경로 반환."""
    safe_name = re.sub(r'[^\w가-힣-]', '_', topic)[:50]
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_p{prompt_id}_{safe_name}.png"
    save_path = IMAGES_DIR / filename
    save_path.write_bytes(image_bytes)
    logger.info(f"이미지 저장: {save_path}")
    return str(save_path)


def save_image_from_telegram(file_bytes: bytes, prompt_id: str) -> str | None:
    """Telegram으로 받은 이미지 저장 및 프롬프트 완료 처리"""
    prompt = get_prompt_by_id(prompt_id)
    if not prompt:
        logger.warning(f"프롬프트 #{prompt_id} 없음")
        return None

    image_path = save_image_from_bytes(file_bytes, prompt['topic'], prompt_id)
    mark_prompt_done(prompt_id, image_path)
    return image_path


# ─── request 모드 — 배치 전송 ──────────────────────────

def send_prompt_batch():
    """
    request 모드 주기 실행.
    data/topics/ 에서 한컷 코너 글감을 스캔해 프롬프트 대기 목록에 추가하고
    현재 pending 상태인 프롬프트 전체를 Telegram으로 전송.
    """
    logger.info("=== 이미지 프롬프트 배치 전송 시작 ===")

    # 한컷 글감 스캔 → 대기 목록에 추가
    topics_dir = DATA_DIR / 'topics'
    for f in sorted(topics_dir.glob('*.json')):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            if data.get('corner') == '한컷':
                add_pending_prompt(
                    topic=data.get('topic', ''),
                    description=data.get('description', ''),
                    article_ref=str(f),
                )
        except Exception:
            pass

    pending = get_pending_prompts('pending')
    selected = get_pending_prompts('selected')
    active = pending + selected

    if not active:
        send_telegram("🎨 현재 이미지 제작 요청이 없습니다.")
        logger.info("대기 프롬프트 없음")
        return

    lines = [
        f"🎨 <b>[이미지 제작 요청 — {len(active)}건]</b>\n",
        "아래 목록에서 제작하실 항목을 선택해주세요.\n",
        f"/imgpick [번호] 로 선택 → 생성형 AI(Midjourney, DALL-E, Stable Diffusion 등)로 제작 → "
        f"이미지를 이 채팅에 전송해주세요.\n",
    ]
    for item in active:
        status_icon = '🔄' if item['status'] == 'selected' else '⏳'
        lines.append(
            f"{status_icon} <b>#{item['id']}</b> {item['topic']}\n"
            f"   📝 <code>{item['prompt'][:200]}...</code>\n"
        )
    lines.append("\n/images — 전체 목록 재확인")

    send_telegram('\n'.join(lines))
    logger.info(f"배치 전송 완료: {len(active)}건")


def send_single_prompt(prompt_id: str):
    """특정 프롬프트 1개를 전체 내용으로 Telegram 전송"""
    prompt = get_prompt_by_id(prompt_id)
    if not prompt:
        send_telegram(f"❌ #{prompt_id} 번 프롬프트를 찾을 수 없습니다.")
        return

    mark_prompt_selected(prompt_id)
    msg = (
        f"🎨 <b>[이미지 제작 — #{prompt['id']}]</b>\n\n"
        f"📌 주제: <b>{prompt['topic']}</b>\n\n"
        f"📝 프롬프트 (복사해서 생성형 AI에 붙여넣으세요):\n\n"
        f"<code>{prompt['prompt']}</code>\n\n"
        f"✅ 이미지 완성 후 <b>이 채팅에 이미지를 전송</b>하면 자동으로 저장됩니다.\n"
        f"(전송 시 캡션에 <code>#{prompt['id']}</code> 를 입력해주세요)"
    )
    send_telegram(msg)
    logger.info(f"단일 프롬프트 전송 #{prompt_id}: {prompt['topic']}")


# ─── auto 모드 ────────────────────────────────────────

def generate_image_auto(prompt: str, topic: str) -> str | None:
    """OpenAI DALL-E 3 API로 이미지 자동 생성"""
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY 없음 — 자동 이미지 생성 불가")
        return None
    try:
        resp = requests.post(
            'https://api.openai.com/v1/images/generations',
            headers={
                'Authorization': f'Bearer {OPENAI_API_KEY}',
                'Content-Type': 'application/json',
            },
            json={
                'model': 'dall-e-3',
                'prompt': prompt,
                'n': 1,
                'size': '1024x1024',
                'quality': 'standard',
            },
            timeout=60,
        )
        resp.raise_for_status()
        image_url = resp.json()['data'][0]['url']
        img_bytes = requests.get(image_url, timeout=30).content
        safe_name = re.sub(r'[^\w가-힣-]', '_', topic)[:50]
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_name}.png"
        save_path = IMAGES_DIR / filename
        save_path.write_bytes(img_bytes)
        logger.info(f"자동 이미지 저장: {save_path}")
        return str(save_path)
    except Exception as e:
        logger.error(f"자동 이미지 생성 실패: {e}")
        return None


# ─── manual 모드 ──────────────────────────────────────

def process_manual_mode(topic: str, description: str = '') -> str:
    """글 발행 시점에 프롬프트 1개 Telegram 전송 (파일 저장은 사용자 직접)"""
    prompt = build_cartoon_prompt(topic, description)
    safe_name = re.sub(r'[^\w가-힣-]', '_', topic)[:50]
    expected_path = IMAGES_DIR / f"{datetime.now().strftime('%Y%m%d')}_{safe_name}.png"
    send_telegram(
        f"🎨 <b>[만평 이미지 요청 — manual]</b>\n\n"
        f"📌 주제: <b>{topic}</b>\n\n"
        f"📝 프롬프트:\n<code>{prompt}</code>\n\n"
        f"이미지 생성 후 아래 경로에 저장해주세요:\n"
        f"<code>{expected_path}</code>"
    )
    logger.info(f"manual 모드 프롬프트 전송: {topic}")
    return str(expected_path)


# ─── 메인 진입점 ──────────────────────────────────────

def process(article: dict) -> str | None:
    """
    한컷 코너 글에 대해 모드에 따라 이미지 처리.
    Returns: 이미지 경로 (request 모드에서는 None — 비동기로 나중에 수령)
    """
    if article.get('corner') != '한컷':
        return None

    topic = article.get('title', '')
    description = article.get('meta', '')
    logger.info(f"이미지봇 실행: {topic} (모드: {IMAGE_MODE})")

    if IMAGE_MODE == 'auto':
        prompt = build_cartoon_prompt(topic, description)
        image_path = generate_image_auto(prompt, topic)
        if image_path:
            send_telegram(
                f"🎨 <b>[자동 이미지 생성 완료]</b>\n\n📌 {topic}\n경로: <code>{image_path}</code>"
            )
        return image_path

    elif IMAGE_MODE == 'request':
        item = add_pending_prompt(topic, description, article_ref=article.get('_source_file', ''))
        send_telegram(
            f"🎨 <b>[이미지 제작 요청 추가됨]</b>\n\n"
            f"📌 주제: <b>{topic}</b>\n"
            f"번호: <b>#{item['id']}</b>\n\n"
            f"/imgpick {item['id']} — 이 주제 프롬프트 받기\n"
            f"/images — 전체 대기 목록 보기"
        )
        return None  # 이미지는 나중에 Telegram으로 수령

    else:  # manual (기본)
        return process_manual_mode(topic, description)


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'batch':
        send_prompt_batch()
    else:
        sample = {'corner': '한컷', 'title': 'AI가 직업을 빼앗는다?', 'meta': ''}
        print(process(sample))
