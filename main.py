import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from database.schema import setup_db
from database.seed_data import seed_db
from telegram_bot.bot import run_bot

def main():
    # 1. Setup Database
    print("Initializing Database...")
    setup_db()
    seed_db()
    
    # 2. Start Telegram Bot
    run_bot()

if __name__ == "__main__":
    main()
