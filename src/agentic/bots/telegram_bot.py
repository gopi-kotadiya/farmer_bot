import asyncio
import atexit
import os
import re
import sys
from pathlib import Path

from telegram import Update
from telegram.error import Conflict
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

from src.utils.globals import globals
from src.utils.logger import logger
from src.agentic.bots.kisan import kisan_bot
from src.agentic.tools.kisan_tools.crop_disease import detect_crop_disease
from src.utils.alert_scheduler import start_alert_scheduler
from src.utils.daily_alert_job import run_digest_for_telegram_id
from src.utils.database import init_db

USER_COLOR = "\033[96m"
ASSISTANT_COLOR = "\033[95m"
RESET_COLOR = "\033[0m"

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TELEGRAM_PID = _REPO_ROOT / "tmp" / "telegram_bot.pid"


def _acquire_single_instance_lock() -> None:
    """Same machine par do `main.py telegram` — Telegram Conflict. Ek hi process."""
    _TELEGRAM_PID.parent.mkdir(parents=True, exist_ok=True)
    if _TELEGRAM_PID.exists():
        try:
            old = int((_TELEGRAM_PID.read_text() or "0").strip())
        except ValueError:
            old = None
        if old and old > 0:
            try:
                os.kill(old, 0)
            except ProcessLookupError:
                _TELEGRAM_PID.unlink(missing_ok=True)
            except PermissionError:
                pass
            else:
                # Zombie PID (<defunct>) should not block fresh bot start.
                stat_path = f"/proc/{old}/stat"
                try:
                    stat_raw = Path(stat_path).read_text(encoding="utf-8")
                    # /proc/<pid>/stat format: pid (comm) state ...
                    parts = stat_raw.split()
                    state = parts[2] if len(parts) > 2 else ""
                    if state == "Z":
                        _TELEGRAM_PID.unlink(missing_ok=True)
                        old = None
                except OSError:
                    _TELEGRAM_PID.unlink(missing_ok=True)
                    old = None
        if old and old > 0:
            try:
                os.kill(old, 0)
            except ProcessLookupError:
                _TELEGRAM_PID.unlink(missing_ok=True)
            except PermissionError:
                pass
            else:
                logger.error(
                    f"Pehle se bot chal rahi hai (pid={old}). Doosri window band karo: kill {old}"
                )
                sys.exit(1)
    _TELEGRAM_PID.write_text(str(os.getpid()), encoding="utf-8")


def _release_single_instance_lock() -> None:
    try:
        if _TELEGRAM_PID.exists() and _TELEGRAM_PID.read_text(encoding="utf-8").strip() == str(
            os.getpid()
        ):
            _TELEGRAM_PID.unlink(missing_ok=True)
    except OSError:
        pass


async def _post_init(application) -> None:
    """Webhook + polling mix se Conflict aata hai — polling se pehle webhook hatao."""
    await application.bot.delete_webhook(drop_pending_updates=True)


async def _on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    err = context.error
    if isinstance(err, Conflict):
        logger.error(
            "Telegram Conflict: isi token par aur koi getUpdates/webhook chal raha hai. "
            "Sab duplicate bot band karo; BotFather me webhook delete / sirf ek `uv run main.py telegram`."
        )
    elif err is not None:
        logger.error(f"Telegram handler error: {err}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    await update.message.reply_text(f"Namaste {user_name}! 🙏 Main KisanBot hoon (Modular Version).")


async def cmd_digest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """One-shot daily digest email + DB alert log (same as scheduled job)."""
    session_id = str(update.effective_user.id)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    ok, msg = await asyncio.to_thread(run_digest_for_telegram_id, session_id)
    await update.message.reply_text(msg if ok else f"Digest nahi bheja: {msg}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_query = update.message.text
    session_id = str(update.effective_user.id)
    print(f"{USER_COLOR}[USER] {session_id} User Message: {user_query}{RESET_COLOR}", flush=True)
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    # Use the modular KisanBot chat logic
    response_text = await kisan_bot.chat(user_query, session_id=session_id)
    print(f"{ASSISTANT_COLOR}[ASSISTANT] {session_id} Assistant: {response_text}{RESET_COLOR}", flush=True)

    graph_match = re.search(r"GRAPH_FILE=([^\n\r]+)", response_text or "")
    graph_path = graph_match.group(1).strip() if graph_match else ""
    reply_text = re.sub(r"\n?GRAPH_FILE=[^\n\r]+", "", response_text or "").strip()
    await update.message.reply_text(reply_text or response_text)
    if graph_path and Path(graph_path).exists():
        try:
            with open(graph_path, "rb") as fp:
                await update.message.reply_photo(photo=fp, caption="Mandi trend graph")
        except Exception as e:
            logger.error(f"Trend graph send failed: {e}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session_id = str(update.effective_user.id)
    caption = (update.message.caption or "").strip()
    print(f"{USER_COLOR}[USER] {session_id} User sent crop image caption={caption}{RESET_COLOR}", flush=True)

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    if not update.message.photo:
        await update.message.reply_text("Photo detect nahi hui. Dobara image bhejo.")
        return

    largest_photo = update.message.photo[-1]
    photo_file = await largest_photo.get_file()
    image_bytes = await photo_file.download_as_bytearray()

    response_text = detect_crop_disease(
        image_bytes=bytes(image_bytes),
        user_prompt=caption,
        session_id=session_id,
    )
    print(f"{ASSISTANT_COLOR}[ASSISTANT] {session_id} Disease Detector: {response_text}{RESET_COLOR}", flush=True)
    await update.message.reply_text(response_text)

def run_telegram_bot():
    if not globals.telegram_token:
        logger.error("No Telegram Token!")
        return

    _acquire_single_instance_lock()
    atexit.register(_release_single_instance_lock)

    init_db()
    start_alert_scheduler()

    app = (
        ApplicationBuilder()
        .token(globals.telegram_token)
        .post_init(_post_init)
        .build()
    )
    app.add_error_handler(_on_error)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("digest", cmd_digest))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    logger.info("🤖 Modular Telegram Bot online!")
    try:
        app.run_polling(drop_pending_updates=True)
    finally:
        _release_single_instance_lock()
