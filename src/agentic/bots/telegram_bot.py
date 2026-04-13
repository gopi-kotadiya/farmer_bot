from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from src.utils.globals import globals
from src.utils.logger import logger
from src.agentic.bots.kisan import kisan_bot

USER_COLOR = "\033[96m"
ASSISTANT_COLOR = "\033[95m"
RESET_COLOR = "\033[0m"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    await update.message.reply_text(f"Namaste {user_name}! 🙏 Main KisanBot hoon (Modular Version).")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_query = update.message.text
    session_id = str(update.effective_user.id)
    print(f"{USER_COLOR}[USER] {session_id} User Message: {user_query}{RESET_COLOR}", flush=True)
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    # Use the modular KisanBot chat logic
    response_text = await kisan_bot.chat(user_query, session_id=session_id)
    print(f"{ASSISTANT_COLOR}[ASSISTANT] {session_id} Assistant: {response_text}{RESET_COLOR}", flush=True)
    
    await update.message.reply_text(response_text)

def run_telegram_bot():
    if not globals.telegram_token:
        logger.error("No Telegram Token!")
        return
        
    app = ApplicationBuilder().token(globals.telegram_token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    logger.info("🤖 Modular Telegram Bot online!")
    app.run_polling()
