import os
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

from database.schema import setup_db
from agent.harness import init_agent
from telegram_bot.bot import run_bot

def main():
    # 1. Setup Database
    print("Initializing Database...")
    setup_db()
    
    # 2. Initialize the Agent with the correct model (must be after dotenv)
    init_agent()
    
    # 3. Start Telegram Bot
    run_bot()

if __name__ == "__main__":
    main()
