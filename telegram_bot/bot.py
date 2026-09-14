import os
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram_bot.handlers import start_handler, new_handler, message_handler

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def run_bot():
    """Start the Telegram bot."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token or token == "your_telegram_bot_token_here":
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables.")
        return

    # Create application
    application = Application.builder().token(token).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("new", new_handler))
    
    # Message handler for all text messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    # Run the bot until the user presses Ctrl-C
    logger.info("Starting Telegram Bot...")
    application.run_polling()
