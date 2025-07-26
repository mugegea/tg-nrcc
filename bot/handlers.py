import os
import asyncio
from collections import defaultdict
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from backend.utils import save_group_to_channel, store_group_mapping, get_group_by_id, generate_link, generate_group_id
import json
INTRO_PATH = os.path.join(os.path.dirname(__file__), '..', 'storage', 'intro.txt')
from telegram import InputMediaPhoto, InputMediaVideo
import uuid
BIND_CHANNELS_PATH = os.path.join(os.path.dirname(__file__), '..', 'storage', 'bind_channels.json')

def add_bound_channel(channel_id):
    channels = get_bound_channels()
    if channel_id not in channels:
        channels.append(channel_id)
        with open(BIND_CHANNELS_PATH, 'w', encoding='utf-8') as f:
            json.dump(channels, f)

def remove_bound_channel(channel_id):
    channels = get_bound_channels()
    if channel_id in channels:
        channels.remove(channel_id)
        with open(BIND_CHANNELS_PATH, 'w', encoding='utf-8') as f:
            json.dump(channels, f)

def get_bound_channels():
    if os.path.exists(BIND_CHANNELS_PATH):
        with open(BIND_CHANNELS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    # 兼容老逻辑，首次用.env
    env_id = os.getenv("CHANNEL_ID")
    return [env_id] if env_id else []

# 读取介绍内容
def get_intro():
    if os.path.exists(INTRO_PATH):
        with open(INTRO_PATH, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return '这是一个资源管理机器人，支持任意内容合并分享。'

# 保存介绍内容
def set_intro(text):
    with open(INTRO_PATH, 'w', encoding='utf-8') as f:
        f.write(text.strip())

user_buffers = defaultdict(list)
user_media_group_buffers = defaultdict(lambda: {'media': [], 'timer': None, 'last_group_id': None})

ADMIN_IDS_PATH = os.path.join(os.path.dirname(__file__), '..', 'storage', 'admin_ids.json')

# 初始化管理员ID列表，默认包含 7389854735
DEFAULT_ADMINS = [7389854735]
def load_admin_ids():
    if os.path.exists(ADMIN_IDS_PATH):
        with open(ADMIN_IDS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return DEFAULT_ADMINS.copy()
def save_admin_ids(ids):
    with open(ADMIN_IDS_PATH, 'w', encoding='utf-8') as f:
        json.dump(ids, f)

BIND_CHANNEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'storage', 'bind_channel.txt')

def set_bound_channel(channel_id):
    with open(BIND_CHANNEL_PATH, 'w', encoding='utf-8') as f:
        f.write(str(channel_id))

def get_bound_channel():
    if os.path.exists(BIND_CHANNEL_PATH):
        with open(BIND_CHANNEL_PATH, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return os.getenv("CHANNEL_ID")

async def bindchannel_handler(update, context):
    user_id = update.effective_user.id
    admin_ids = load_admin_ids()
    if user_id not in admin_ids:
        await update.message.reply_text("无权限，仅管理员可用。"); return
    if not context.args or not context.args[0].startswith('-100'):
        await update.message.reply_text("用法：/bindchannel <频道ID>\n如：/bindchannel -100xxxxxxxxxx"); return
    set_bound_channel(context.args[0])
    await update.message.reply_text(f"已绑定频道：{context.args[0]}")

async def showchannel_handler(update, context):
    channel_id = get_bound_channel()
    await update.message.reply_text(f"当前绑定频道ID：{channel_id}")

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payload = context.args[0] if context.args else None
    # 移除主菜单按钮
    if payload:
        group = get_group_by_id(payload)
        if group:
            # 先发送欢迎消息，引导用户点击开始
            await update.message.reply_text("🎉 欢迎！点击下方按钮开始获取内容：")
            
            # 创建内联键盘，让用户一键开始
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 开始获取内容", callback_data=f"get_content_{payload}")]
            ])
            await update.message.reply_text("请点击下方按钮获取内容：", reply_markup=keyboard)
        else:
            await update.message.reply_text("资源未找到或链接已失效。")
    else:
        await update.message.reply_text(
            f"欢迎！请发送任意内容，发送多条后点击下方“完成”按钮，我会帮你生成访问链接并备份到频道。\n\n{get_intro()}"
        )

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "【功能说明】\n"
        "- 支持任意内容（文本、图片、视频等）发送给机器人，生成唯一访问链接\n"
        "- 多条内容合并为一个链接，点击“完成”后生成\n"
        "- 所有内容自动备份到频道\n"
        "- 链接可分享，其他用户点击后机器人自动发送原内容\n"
        "\n【指令列表】\n"
        "/start [参数] - 获取资源或显示欢迎信息\n"
        "/help - 显示帮助和功能说明\n"
        "/intro - 查看机器人介绍\n"
        "/setintro <内容> - 设置机器人介绍（仅管理员）\n"
        "发送内容+点击“完成” - 生成合并内容的访问链接"
    )
    await update.message.reply_text(help_text)

async def intro_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_intro())

async def setintro_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    admin_ids = load_admin_ids()
    if user_id not in admin_ids:
        await update.message.reply_text("无权限，仅管理员可用。")
        return
    text = ' '.join(context.args)
    if not text:
        await update.message.reply_text("用法：/setintro 你的介绍内容")
        return
    set_intro(text)
    await update.message.reply_text("介绍内容已更新！")

async def addadmin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    admin_ids = load_admin_ids()
    if user_id not in admin_ids:
        await update.message.reply_text("无权限，仅管理员可用。")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("用法：/addadmin <Telegram用户ID>")
        return
    new_admin = int(context.args[0])
    if new_admin in admin_ids:
        await update.message.reply_text("该用户已是管理员。"); return
    admin_ids.append(new_admin)
    save_admin_ids(admin_ids)
    await update.message.reply_text(f"已添加管理员：{new_admin}")

async def deladmin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    admin_ids = load_admin_ids()
    if user_id not in admin_ids:
        await update.message.reply_text("无权限，仅管理员可用。"); return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("用法：/deladmin <Telegram用户ID>"); return
    del_admin = int(context.args[0])
    if del_admin not in admin_ids:
        await update.message.reply_text("该用户不是管理员。"); return
    if del_admin == user_id:
        await update.message.reply_text("不能删除自己。"); return
    admin_ids.remove(del_admin)
    save_admin_ids(admin_ids)
    await update.message.reply_text(f"已移除管理员：{del_admin}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == "help":
        await help_handler(query, context)
        await query.answer()
    elif query.data == "start":
        await start_handler(query, context)
        await query.answer()
    elif query.data == "admin_manage":
        await query.edit_message_text("管理员管理：\n请发送 /addadmin <Telegram用户ID> 来添加管理员。\n只有管理员可用。")
        await query.answer()
    elif query.data.startswith("get_content_"):
        # 处理获取内容按钮
        group_id = query.data.replace("get_content_", "")
        group = get_group_by_id(group_id)
        if group:
            await restore_group_to_user(group, context.bot, query.message.chat_id)
            await query.edit_message_text("✅ 内容已发送！")
        else:
            await query.edit_message_text("❌ 内容未找到或已失效！")
        await query.answer()

async def content_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.message
    media_group_id = getattr(message, 'media_group_id', None)
    if media_group_id:
        # 收集media group
        buf = user_media_group_buffers[user_id]
        buf['media'].append(update)
        buf['last_group_id'] = media_group_id
        # 重置等待定时器
        if buf['timer']:
            buf['timer'].cancel()
        buf['timer'] = asyncio.create_task(media_group_wait_and_confirm(user_id, context))
    else:
        user_buffers[user_id].append(update)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("完成", callback_data="finish"), InlineKeyboardButton("取消", callback_data="cancel")]
        ])
        await update.message.reply_text("已收到，继续发送或点击完成。", reply_markup=keyboard)

async def media_group_wait_and_confirm(user_id, context):
    await asyncio.sleep(2.5)  # 等待2.5秒，判断用户是否还在发
    buf = user_media_group_buffers[user_id]
    user_buffers[user_id].extend(buf['media'])
    buf['media'].clear()
    buf['timer'] = None
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("完成", callback_data="finish"), InlineKeyboardButton("取消", callback_data="cancel")]
    ])
    # 只回复一次
    last_update = user_buffers[user_id][-1]
    await last_update.message.reply_text("已收到，继续发送或点击完成。", reply_markup=keyboard)

# 修改send_group_to_channel支持多频道
async def send_group_to_channel(grouped, bot):
    channel_ids = get_bound_channels()
    for channel_id in channel_ids:
        for item in grouped:
            await send_item_to_chat(item, bot, int(channel_id))

pending_submissions = {}  # {submission_id: {'user_id':..., 'grouped':..., 'chat_id':..., 'message_id':..., 'admin_msg_ids': {admin_id: msg_id}}}

async def finish_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    admin_ids = load_admin_ids()
    buffer = user_buffers.get(user_id, [])
    grouped = []
    i = 0
    while i < len(buffer):
        msg = buffer[i]
        message = getattr(msg, 'message', None) or getattr(msg, 'effective_message', None) or msg
        media_group_id = getattr(message, 'media_group_id', None)
        if media_group_id:
            group_items = []
            while i < len(buffer):
                m = getattr(buffer[i], 'message', None) or getattr(buffer[i], 'effective_message', None) or buffer[i]
                if getattr(m, 'media_group_id', None) == media_group_id:
                    group_items.append(serialize_message(m))
                    i += 1
                else:
                    break
            grouped.append({'type': 'media_group', 'items': group_items})
        else:
            grouped.append(serialize_message(message))
            i += 1
    if not grouped:
        await query.answer("没有待合并的内容。", show_alert=True)
        return
    user_buffers[user_id].clear()
    if user_id in admin_ids:
        await query.edit_message_text("正在上传并生成链接，请稍候…")
        await send_group_to_channel(grouped, context.bot)
        group_id = generate_group_id()
        store_group_mapping(group_id, grouped)
        link = generate_link(group_id)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("点击访问内容", url=link)]
        ])
        await context.bot.send_message(chat_id=query.message.chat_id, text=f"✅ 链接已生成 👇\n{link}", reply_markup=keyboard)
        await send_link_to_backup_channels(link, context.bot)
        await query.answer()
    else:
        await query.edit_message_text("内容已提交，等待管理员审核。")
        submission_id = str(uuid.uuid4())
        pending_submissions[submission_id] = {
            'user_id': user_id,
            'grouped': grouped,
            'chat_id': query.message.chat_id,
            'message_id': query.message.message_id,
            'admin_msg_ids': {}
        }
        admin_ids = load_admin_ids()
        for admin_id in admin_ids:
            msg_id = await send_group_to_admin_for_review(grouped, context.bot, admin_id, submission_id, user_id)
            pending_submissions[submission_id]['admin_msg_ids'][admin_id] = msg_id
        await query.answer()

async def send_group_to_admin_for_review(grouped, bot, admin_id, submission_id, user_id):
    # 获取用户名
    user = await bot.get_chat(user_id)
    username = user.username if hasattr(user, 'username') and user.username else None
    if username:
        user_display = f'@{username} (ID:{user_id})'
    else:
        user_display = f"ID:{user_id}"
    # 先发一条文本消息带审核按钮
    review_text = f"\u2728 <b>投稿审核</b>\n用户: {user_display}\n\n请审核以下内容："
    reply_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ 通过", callback_data=f"approve_{submission_id}"),
            InlineKeyboardButton("❌ 拒绝", callback_data=f"reject_{submission_id}")
        ]
    ])
    sent = await bot.send_message(chat_id=admin_id, text=review_text, reply_markup=reply_markup, parse_mode='HTML')
    # 再推送内容本体
    for item in grouped:
        await send_item_to_chat(item, bot, admin_id)
    return sent.message_id

async def audit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    admin_id = query.from_user.id
    admin_ids = load_admin_ids()
    # 获取管理员用户名
    admin_user = await context.bot.get_chat(admin_id)
    admin_username = admin_user.username if hasattr(admin_user, 'username') and admin_user.username else None
    if admin_username:
        admin_display = f"@{admin_username} (ID:{admin_id})"
    else:
        admin_display = f"ID:{admin_id}"
    if admin_id not in admin_ids:
        await query.answer("无权限，仅管理员可用。", show_alert=True)
        return
    if data.startswith("approve_") or data.startswith("reject_"):
        action = '通过' if data.startswith("approve_") else '拒绝'
        emoji = '✅' if action == '通过' else '❌'
        submission_id = data.split('_', 1)[1]
        submission = pending_submissions.pop(submission_id, None)
        if not submission:
            await query.answer("该内容已被其他管理员审核。", show_alert=True)
            return
        grouped = submission['grouped']
        user_id = submission['user_id']
        chat_id = submission['chat_id']
        admin_msg_ids = submission.get('admin_msg_ids', {})
        # 通知所有管理员，按钮变为状态提示
        for aid, msg_id in admin_msg_ids.items():
            try:
                await context.bot.edit_message_text(
                    chat_id=aid,
                    message_id=msg_id,
                    text=f"{emoji} <b>该投稿已被管理员 {admin_display} 审核{action}</b>",
                    parse_mode='HTML'
                )
            except Exception:
                pass
        if action == '通过':
            await send_group_to_channel(grouped, context.bot)
            group_id = generate_group_id()
            store_group_mapping(group_id, grouped)
            link = generate_link(group_id)
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("点击访问内容", url=link)]
            ])
            await context.bot.send_message(chat_id=chat_id, text=f"✅ 你的内容已通过审核，链接如下：\n{link}", reply_markup=keyboard)
            await send_link_to_backup_channels(link, context.bot)
            await context.bot.send_message(chat_id=admin_id, text="已通过并推送到频道。")
            await query.answer("已通过")
        else:
            await context.bot.send_message(chat_id=chat_id, text="很抱歉，你的内容未通过管理员审核。")
            await context.bot.send_message(chat_id=admin_id, text="已拒绝该内容。")
            await query.answer("已拒绝")

# 序列化所有主流类型

def serialize_message(m):
    if m.text:
        return {'type': 'text', 'text': m.text}
    if m.photo:
        return {'type': 'photo', 'file_id': m.photo[-1].file_id, 'caption': m.caption or None}
    if m.video:
        return {'type': 'video', 'file_id': m.video.file_id, 'caption': m.caption or None}
    if m.document:
        return {'type': 'document', 'file_id': m.document.file_id, 'caption': m.caption or None, 'file_name': getattr(m.document, 'file_name', None)}
    if m.audio:
        return {'type': 'audio', 'file_id': m.audio.file_id, 'caption': m.caption or None}
    if m.voice:
        return {'type': 'voice', 'file_id': m.voice.file_id}
    if m.sticker:
        return {'type': 'sticker', 'file_id': m.sticker.file_id}
    if m.animation:
        return {'type': 'animation', 'file_id': m.animation.file_id, 'caption': m.caption or None}
    if m.location:
        return {'type': 'location', 'latitude': m.location.latitude, 'longitude': m.location.longitude}
    if m.contact:
        return {'type': 'contact', 'phone_number': m.contact.phone_number, 'first_name': m.contact.first_name, 'last_name': getattr(m.contact, 'last_name', None)}
    if m.poll:
        return {'type': 'poll', 'question': m.poll.question, 'options': [o.text for o in m.poll.options]}
    if m.dice:
        return {'type': 'dice', 'emoji': m.dice.emoji, 'value': m.dice.value}
    if m.venue:
        return {'type': 'venue', 'latitude': m.venue.location.latitude, 'longitude': m.venue.location.longitude, 'title': m.venue.title, 'address': m.venue.address}
    if m.video_note:
        return {'type': 'video_note', 'file_id': m.video_note.file_id}
    return {'type': 'unsupported'}

async def restore_group_to_user(group, bot, chat_id):
    for item in group['items']:
        await send_item_to_chat(item, bot, chat_id)

async def send_item_to_chat(item, bot, chat_id, reply_markup=None, prefix=None):
    from telegram import InputMediaPhoto, InputMediaVideo
    if item['type'] == 'media_group':
        media = []
        for m in item['items']:
            if m['type'] == 'photo':
                media.append(InputMediaPhoto(media=m['file_id'], caption=m.get('caption')))
            elif m['type'] == 'video':
                media.append(InputMediaVideo(media=m['file_id'], caption=m.get('caption')))
        if media:
            await bot.send_media_group(chat_id, media)
    elif item['type'] == 'photo':
        await bot.send_photo(chat_id, item['file_id'], caption=(prefix or '') + (item.get('caption') or '') if prefix or item.get('caption') else None, reply_markup=reply_markup)
    elif item['type'] == 'video':
        await bot.send_video(chat_id, item['file_id'], caption=(prefix or '') + (item.get('caption') or '') if prefix or item.get('caption') else None, reply_markup=reply_markup)
    elif item['type'] == 'text':
        await bot.send_message(chat_id, (prefix or '') + item['text'], reply_markup=reply_markup)
    elif item['type'] == 'document':
        await bot.send_document(chat_id, item['file_id'], caption=(prefix or '') + (item.get('caption') or '') if prefix or item.get('caption') else None, filename=item.get('file_name'), reply_markup=reply_markup)
    elif item['type'] == 'audio':
        await bot.send_audio(chat_id, item['file_id'], caption=(prefix or '') + (item.get('caption') or '') if prefix or item.get('caption') else None, reply_markup=reply_markup)
    elif item['type'] == 'voice':
        await bot.send_voice(chat_id, item['file_id'], reply_markup=reply_markup)
    elif item['type'] == 'sticker':
        await bot.send_sticker(chat_id, item['file_id'], reply_markup=reply_markup)
    elif item['type'] == 'animation':
        await bot.send_animation(chat_id, item['file_id'], caption=(prefix or '') + (item.get('caption') or '') if prefix or item.get('caption') else None, reply_markup=reply_markup)
    elif item['type'] == 'location':
        await bot.send_location(chat_id, item['latitude'], item['longitude'], reply_markup=reply_markup)
    elif item['type'] == 'contact':
        await bot.send_contact(chat_id, item['phone_number'], item['first_name'], last_name=item.get('last_name'), reply_markup=reply_markup)
    elif item['type'] == 'poll':
        await bot.send_message(chat_id, (prefix or '') + f"[投票] {item['question']}\n选项: {', '.join(item['options'])}", reply_markup=reply_markup)
    elif item['type'] == 'dice':
        await bot.send_dice(chat_id, emoji=item['emoji'], reply_markup=reply_markup)
    elif item['type'] == 'venue':
        await bot.send_venue(chat_id, item['latitude'], item['longitude'], item['title'], item['address'], reply_markup=reply_markup)
    elif item['type'] == 'video_note':
        await bot.send_video_note(chat_id, item['file_id'], reply_markup=reply_markup)
    else:
        await bot.send_message(chat_id, (prefix or '') + '[不支持的内容类型]', reply_markup=reply_markup)

async def addchannel_handler(update, context):
    user_id = update.effective_user.id
    admin_ids = load_admin_ids()
    if user_id not in admin_ids:
        await update.message.reply_text("无权限，仅管理员可用。"); return
    if not context.args or not context.args[0].startswith('-100'):
        await update.message.reply_text("用法：/addchannel <频道ID>\n如：/addchannel -100xxxxxxxxxx"); return
    add_bound_channel(context.args[0])
    await update.message.reply_text(f"已添加绑定频道：{context.args[0]}")

async def rmchannel_handler(update, context):
    user_id = update.effective_user.id
    admin_ids = load_admin_ids()
    if user_id not in admin_ids:
        await update.message.reply_text("无权限，仅管理员可用。"); return
    if not context.args or not context.args[0].startswith('-100'):
        await update.message.reply_text("用法：/rmchannel <频道ID>\n如：/rmchannel -100xxxxxxxxxx"); return
    remove_bound_channel(context.args[0])
    await update.message.reply_text(f"已移除绑定频道：{context.args[0]}")

async def listchannels_handler(update, context):
    channels = get_bound_channels()
    await update.message.reply_text("当前绑定频道ID列表：\n" + '\n'.join(channels) if channels else "无绑定频道")

BACKUP_CHANNELS_PATH = os.path.join(os.path.dirname(__file__), '..', 'storage', 'backup_channels.json')

def get_backup_channels():
    if os.path.exists(BACKUP_CHANNELS_PATH):
        with open(BACKUP_CHANNELS_PATH, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    return []

def add_backup_channel(channel_id):
    channels = get_backup_channels()
    if channel_id not in channels:
        channels.append(channel_id)
        with open(BACKUP_CHANNELS_PATH, 'w', encoding='utf-8-sig') as f:
            json.dump(channels, f)

def remove_backup_channel(channel_id):
    channels = get_backup_channels()
    if channel_id in channels:
        channels.remove(channel_id)
        with open(BACKUP_CHANNELS_PATH, 'w', encoding='utf-8-sig') as f:
            json.dump(channels, f)

async def addbackupchannel_handler(update, context):
    user_id = update.effective_user.id
    admin_ids = load_admin_ids()
    if user_id not in admin_ids:
        await update.message.reply_text("无权限，仅管理员可用。"); return
    if not context.args or not context.args[0].startswith('-100'):
        await update.message.reply_text("用法：/addbackupchannel <频道ID>\n如：/addbackupchannel -100xxxxxxxxxx"); return
    add_backup_channel(context.args[0])
    await update.message.reply_text(f"已添加备用频道：{context.args[0]}")

async def rmbackupchannel_handler(update, context):
    user_id = update.effective_user.id
    admin_ids = load_admin_ids()
    if user_id not in admin_ids:
        await update.message.reply_text("无权限，仅管理员可用。"); return
    if not context.args or not context.args[0].startswith('-100'):
        await update.message.reply_text("用法：/rmbackupchannel <频道ID>\n如：/rmbackupchannel -100xxxxxxxxxx"); return
    remove_backup_channel(context.args[0])
    await update.message.reply_text(f"已移除备用频道：{context.args[0]}")

async def listbackupchannels_handler(update, context):
    channels = get_backup_channels()
    await update.message.reply_text("当前备用频道ID列表：\n" + '\n'.join(channels) if channels else "无备用频道")

async def send_link_to_backup_channels(link, bot):
    channels = get_backup_channels()
    for channel_id in channels:
        await bot.send_message(chat_id=int(channel_id), text=f"✅ 链接已生成 👇\n{link}")

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    user_buffers[user_id].clear()
    user_media_group_buffers[user_id]['media'].clear()
    user_media_group_buffers[user_id]['timer'] = None
    await query.edit_message_text("已取消。")
    await query.answer()

# 指令描述字典
COMMAND_DESCRIPTIONS = {
    '/start': '获取资源或显示欢迎信息',
    '/help': '显示帮助和功能说明',
    '/intro': '查看机器人介绍',
    '/setintro': '设置机器人介绍（仅管理员）',
    '/addadmin': '添加管理员（仅管理员）',
    '/deladmin': '删除管理员（仅管理员）',
    '/addchannel': '添加绑定频道（仅管理员）',
    '/rmchannel': '移除绑定频道（仅管理员）',
    '/listchannels': '列出所有绑定频道',
    '/addbackupchannel': '添加备用频道（仅管理员）',
    '/rmbackupchannel': '移除备用频道（仅管理员）',
    '/listbackupchannels': '列出所有备用频道',
    '/qbzhiling': '显示所有机器人指令及其描述',
}

async def qbzhiling_handler(update, context):
    text = '【机器人指令列表】\n'
    for cmd, desc in COMMAND_DESCRIPTIONS.items():
        text += f'{cmd} - {desc}\n'
    await update.message.reply_text(text)

def register_handlers(application):
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("intro", intro_handler))
    application.add_handler(CommandHandler("setintro", setintro_handler))
    application.add_handler(CommandHandler("addadmin", addadmin_handler))
    application.add_handler(CommandHandler("deladmin", deladmin_handler))
    application.add_handler(CommandHandler("addchannel", addchannel_handler))
    application.add_handler(CommandHandler("rmchannel", rmchannel_handler))
    application.add_handler(CommandHandler("listchannels", listchannels_handler))
    application.add_handler(CommandHandler("addbackupchannel", addbackupchannel_handler))
    application.add_handler(CommandHandler("rmbackupchannel", rmbackupchannel_handler))
    application.add_handler(CommandHandler("listbackupchannels", listbackupchannels_handler))
    application.add_handler(CommandHandler("qbzhiling", qbzhiling_handler))
    application.add_handler(MessageHandler(filters.ALL, content_handler))
    application.add_handler(CallbackQueryHandler(finish_handler, pattern="^finish$"))
    application.add_handler(CallbackQueryHandler(audit_handler, pattern="^(approve_|reject_).*$"))
    application.add_handler(CallbackQueryHandler(cancel_handler, pattern="^cancel$"))
    application.add_handler(CallbackQueryHandler(button_handler, pattern="^(help|start|admin_manage)$")) 
