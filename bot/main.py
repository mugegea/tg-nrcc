import os
from dotenv import load_dotenv
from telegram.ext import Application
from bot.handlers import register_handlers

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

application = Application.builder().token(BOT_TOKEN).build()
register_handlers(application)

if __name__ == "__main__":
    application.run_polling() 