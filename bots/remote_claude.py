"""
Remote Claude Bot
텔레그램 메시지를 Claude Agent SDK에 전달하고 결과를 돌려보냅니다.
실행: python bots/remote_claude.py
"""
import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

load_dotenv(dotenv_path=Path(__file__).parent.parent / '.env')

BASE_DIR = Path(__file__).parent.parent
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = int(os.getenv('TELEGRAM_CHAT_ID', '0'))
REMOTE_CLAUDE_POLLING_ENABLED = os.getenv('REMOTE_CLAUDE_POLLING_ENABLED', '').lower() in {'1', 'true', 'yes', 'on'}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)

MAX_MSG_LEN = 4000


def split_message(text: str) -> list[str]:
    chunks = []
    while len(text) > MAX_MSG_LEN:
        chunks.append(text[:MAX_MSG_LEN])
        text = text[MAX_MSG_LEN:]
    if text:
        chunks.append(text)
    return chunks


async def run_claude(prompt: str) -> str:
    result_text = ""
    try:
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                cwd=str(BASE_DIR),
                allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
                permission_mode="bypassPermissions",
                max_turns=30,
            )
        ):
            if isinstance(message, ResultMessage):
                result_text = message.result
    except Exception as e:
        result_text = f"오류: {e}"
    return result_text or "(완료)"


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != TELEGRAM_CHAT_ID:
        return

    prompt = update.message.text.strip()
    logger.info(f"명령 수신: {prompt[:80]}")

    await update.message.reply_text("처리 중...")
    await context.bot.send_chat_action(chat_id=TELEGRAM_CHAT_ID, action="typing")

    result = await run_claude(prompt)

    for chunk in split_message(result):
        await update.message.reply_text(chunk)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != TELEGRAM_CHAT_ID:
        return
    await update.message.reply_text(
        "Remote Claude Bot\n\n"
        "자연어로 아무 지시나 입력하세요.\n\n"
        "예시:\n"
        "• scheduler.py 상태 확인해줘\n"
        "• 수집봇 지금 실행해줘\n"
        "• .env 파일 내용 보여줘\n"
        "• requirements.txt에 패키지 추가해줘\n"
        "• 오늘 로그 확인해줘\n\n"
        "/help — 이 메시지"
    )


def main():
    if not REMOTE_CLAUDE_POLLING_ENABLED:
        logger.info("Remote Claude Bot polling 비활성화 — 기본 운영은 scheduler.py Telegram 리스너 사용")
        return

    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN이 없습니다.")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler('help', cmd_help))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Chat(TELEGRAM_CHAT_ID),
        handle_message
    ))

    logger.info(f"Remote Claude Bot 시작 (chat_id={TELEGRAM_CHAT_ID})")
    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
