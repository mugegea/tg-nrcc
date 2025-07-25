import os
import sqlite3
import json
import string
import random
from datetime import datetime
from telegram import InputMediaPhoto, InputMediaVideo

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage", "mapping.db"))
if not os.path.exists(os.path.dirname(DB_PATH)):
    os.makedirs(os.path.dirname(DB_PATH))
conn = sqlite3.connect(DB_PATH, check_same_thread=False)

# 初始化表结构
conn.execute("""
CREATE TABLE IF NOT EXISTS ContentGroup (
    group_id TEXT PRIMARY KEY,
    channel_msg_ids TEXT,
    created_at DATETIME
);
""")

# 生成唯一 group_id
def generate_group_id(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# 新的内容组存储结构
# [{type: 'photo', file_id: ..., caption: ...}, {type: 'text', text: ...}, ...]

def store_group_mapping(group_id, group_items):
    conn.execute(
        "INSERT OR REPLACE INTO ContentGroup VALUES (?, ?, ?)",
        (group_id, json.dumps(group_items, ensure_ascii=False), datetime.utcnow())
    )
    conn.commit()

def get_group_by_id(group_id):
    cursor = conn.execute("SELECT channel_msg_ids FROM ContentGroup WHERE group_id = ?", (group_id,))
    row = cursor.fetchone()
    if not row:
        return None
    group_items = json.loads(row[0])
    return {'group_id': group_id, 'items': group_items}

async def save_group_to_channel(messages, bot):
    channel_id = int(os.getenv("CHANNEL_ID"))
    group_items = []
    for msg in messages:
        message = getattr(msg, 'message', None) or getattr(msg, 'effective_message', None) or msg
        # 还原类型和内容
        if message.photo:
            group_items.append({'type': 'photo', 'file_id': message.photo[-1].file_id, 'caption': message.caption or ''})
            await bot.send_photo(channel_id, message.photo[-1].file_id, caption=message.caption or None)
        elif message.video:
            group_items.append({'type': 'video', 'file_id': message.video.file_id, 'caption': message.caption or ''})
            await bot.send_video(channel_id, message.video.file_id, caption=message.caption or None)
        elif message.text:
            group_items.append({'type': 'text', 'text': message.text})
            await bot.send_message(channel_id, message.text)
        # 可扩展更多类型
    group_id = generate_group_id()
    return group_id, group_items

def generate_link(group_id):
    bot_username = os.getenv("BOT_USERNAME")
    return f"https://t.me/{bot_username}?start={group_id}" 