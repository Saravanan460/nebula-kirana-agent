import os
import re
import html

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from agent.harness import agent, AgentDeps, get_fallback_models
from tools.preferences import clear_conversation_memory
from tools.file_queue import pop_files
from database.seed_data import seed_db

# Telegram max message length
MAX_MSG_LEN = 4096

# Simple in-memory storage for message history per chat to enable multi-turn
# For a production app this should be in SQLite, but memory is fine for the 5-day task
# as long as core data (bills, stock) survives restart.
CHAT_HISTORIES = {}

async def _send_long_text(update: Update, text: str):
    """Split and send text that may exceed Telegram's 4096 char limit."""
    # Strip any [FILE_READY:...] markers the LLM might echo
    text = re.sub(r'\[FILE_READY:.+?\]', '', text).strip()

    # Send as HTML (convert **bold** → <b>bold</b>)
    formatted_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    formatted_text = formatted_text.replace('<', '&lt;').replace('>', '&gt;') if '<b>' not in formatted_text else formatted_text
    
    for i in range(0, len(formatted_text), MAX_MSG_LEN):
        try:
            await update.message.reply_text(formatted_text[i:i + MAX_MSG_LEN], parse_mode=ParseMode.HTML)
        except Exception:
            await update.message.reply_text(formatted_text[i:i + MAX_MSG_LEN])

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    chat_id = update.effective_chat.id
    CHAT_HISTORIES[chat_id] = []
    # Seed the products for this user
    seed_db(chat_id)
    await update.message.reply_text(
        "👋 Welcome to Nebula Kirana Agent!\n\n"
        "I am your operations agent. You can tell me to receive stock, cut bills, check khata, and more."
    )

async def new_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /new command to clear conversation history but keep preferences."""
    chat_id = update.effective_chat.id
    CHAT_HISTORIES[chat_id] = []
    clear_conversation_memory(chat_id)
    # Cancel any open draft bills
    from tools.billing import cancel_bill
    cancel_bill(chat_id)
    await update.message.reply_text(
        "🧹 Conversation history cleared and drafts cancelled. Your preferences are saved. What would you like to do?"
    )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all natural language messages."""
    chat_id = update.effective_chat.id
    user_text = update.message.text
    
    if not user_text:
        return
        
    # Get or initialize history
    if chat_id not in CHAT_HISTORIES:
        CHAT_HISTORIES[chat_id] = []
        
    # Send "typing..." action
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    try:
        # Run agent with automatic model fallback on rate limits
        deps = AgentDeps(chat_id=chat_id, message_id=update.message.message_id)
        fallback_model = get_fallback_models()
        
        agent._model = fallback_model
        result = await agent.run(
            user_text,
            deps=deps,
            message_history=CHAT_HISTORIES[chat_id]
        )
        
        # Update history (keep last 20 messages to avoid context bloat)
        all_msgs = result.all_messages()
        CHAT_HISTORIES[chat_id] = all_msgs[-20:] if len(all_msgs) > 20 else all_msgs
        
        reply_text = result.output
        
        # Send the text reply
        if reply_text.strip():
            await _send_long_text(update, reply_text.strip())
        
        # Send any queued files (PDF, PPTX) via the side-channel
        pending = pop_files(chat_id)
        for file_path in pending:
            try:
                with open(file_path, 'rb') as f:
                    await update.message.reply_document(
                        document=f,
                        filename=os.path.basename(file_path)
                    )
            except Exception as e:
                await update.message.reply_text(f"❌ Failed to send document: {str(e)}")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = str(e)
        if len(error_msg) > 200:
            error_msg = error_msg[:200] + "..."
        await update.message.reply_text(f"❌ An error occurred: {error_msg}")
