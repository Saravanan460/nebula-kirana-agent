import os
import re
from telegram import Update
from telegram.ext import ContextTypes
from agent.harness import agent, AgentDeps
from tools.preferences import clear_conversation_memory

# Telegram max message length
MAX_MSG_LEN = 4096

# Simple in-memory storage for message history per chat to enable multi-turn
# For a production app this should be in SQLite, but memory is fine for the 5-day task 
# as long as core data (bills, stock) survives restart.
CHAT_HISTORIES = {}

async def _send_long_text(update: Update, text: str):
    """Split and send text that may exceed Telegram's 4096 char limit."""
    for i in range(0, len(text), MAX_MSG_LEN):
        await update.message.reply_text(text[i:i + MAX_MSG_LEN])

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    chat_id = update.effective_chat.id
    CHAT_HISTORIES[chat_id] = []
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
        # Run agent
        deps = AgentDeps(chat_id=chat_id, message_id=update.message.message_id)
        result = await agent.run(
            user_text,
            deps=deps,
            message_history=CHAT_HISTORIES[chat_id]
        )
        
        # Update history (keep last 20 messages to avoid context bloat)
        all_msgs = result.all_messages()
        CHAT_HISTORIES[chat_id] = all_msgs[-20:] if len(all_msgs) > 20 else all_msgs
        
        reply_text = result.data
        
        # Check for file attachments
        file_match = re.search(r"\[FILE_READY:(.+?)\]", reply_text)
        if file_match:
            file_path = file_match.group(1)
            reply_text = reply_text.replace(file_match.group(0), "")
            
            # Send text first
            if reply_text.strip():
                await _send_long_text(update, reply_text.strip())
                
            # Send Document
            try:
                await update.message.reply_document(document=open(file_path, 'rb'))
            except Exception as e:
                await update.message.reply_text(f"❌ Failed to send document: {str(e)}")
        else:
            # Just send text
            await _send_long_text(update, reply_text)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = str(e)
        if len(error_msg) > 200:
            error_msg = error_msg[:200] + "..."
        await update.message.reply_text(f"❌ An error occurred: {error_msg}")
