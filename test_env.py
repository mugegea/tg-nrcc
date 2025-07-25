from dotenv import load_dotenv
import os

load_dotenv()
print("BOT_TOKEN:", os.getenv("BOT_TOKEN"))
print("需要的环境变量有：BOT_TOKEN, CHANNEL_ID, BOT_USERNAME") 