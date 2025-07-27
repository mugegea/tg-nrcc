import os
import asyncio
from collections import defaultdict
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, MessageHandler, CallbackQueryHandler, filters
from backend.utils import save_group_to_channel, store_group_mapping, get_group_by_id, generate_link, generate_group_id
import json
from datetime import datetime
INTRO_PATH = os.path.join(os.path.dirname(__file__), '..', 'storage', 'intro.txt')
from telegram import InputMediaPhoto, InputMediaVideo
import uuid
BIND_CHANNELS_PATH = os.path.join(os.path.dirname(__file__), '..', 'storage', 'bind_channels.json')
FORCE_FOLLOW_PATH = os.path.join(os.path.dirname(__file__), '..', 'storage', 'force_follow.json')
FOLLOW_STATS_PATH = os.path.join(os.path.dirname(__file__), '..', 'storage', 'follow_stats.json')
USERS_PATH = os.path.join(os.path.dirname(__file__), '..', 'storage', 'users.json')
BROADCAST_HISTORY_PATH = os.path.join(os.path.dirname(__file__), '..', 'storage', 'broadcast_history.json')

# 用户管理功能
def get_users():
    """获取所有用户列表"""
    if os.path.exists(USERS_PATH):
        with open(USERS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def add_user(user_id, username=None, first_name=None, last_name=None):
    """添加用户到数据库"""
    users = get_users()
    user_info = {
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "joined_at": datetime.now().isoformat(),
        "last_active": datetime.now().isoformat()
    }
    
    # 检查用户是否已存在
    existing_user = next((user for user in users if user["user_id"] == user_id), None)
    if existing_user:
        # 更新用户信息
        existing_user.update(user_info)
    else:
        # 添加新用户
        users.append(user_info)
    
    with open(USERS_PATH, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def update_user_activity(user_id):
    """更新用户最后活跃时间"""
    users = get_users()
    for user in users:
        if user["user_id"] == user_id:
            user["last_active"] = datetime.now().isoformat()
            break
    
    with open(USERS_PATH, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def get_broadcast_history():
    """获取广播历史"""
    if os.path.exists(BROADCAST_HISTORY_PATH):
        with open(BROADCAST_HISTORY_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_broadcast_history(broadcast_info):
    """保存广播历史"""
    history = get_broadcast_history()
    history.append(broadcast_info)
    
    # 只保留最近50条记录
    if len(history) > 50:
        history = history[-50:]
    
    with open(BROADCAST_HISTORY_PATH, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

# 广播缓冲区
broadcast_buffers = defaultdict(list)
broadcast_media_group_buffers = defaultdict(lambda: {'media': [], 'timer': None, 'last_group_id': None})

# 广播模式状态管理
broadcast_mode_users = set()  # 记录哪些用户在广播模式中

# 通知缓存
notification_cache = {}  # {user_id: notification_text}

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

def get_force_follow_config():
    if os.path.exists(FORCE_FOLLOW_PATH):
        with open(FORCE_FOLLOW_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"enabled": False, "channel_id": "", "channel_username": ""}

def save_force_follow_config(config):
    with open(FORCE_FOLLOW_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

async def check_user_in_channel(bot, user_id, channel_id):
    """检查用户是否在指定频道中"""
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"检查用户频道状态失败: {e}")
        return False

def get_follow_stats():
    """获取关注统计数据"""
    if os.path.exists(FOLLOW_STATS_PATH):
        with open(FOLLOW_STATS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"total_follows": 0, "today_follows": 0, "last_reset_date": "", "follow_records": []}

def save_follow_stats(stats):
    """保存关注统计数据"""
    with open(FOLLOW_STATS_PATH, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

def record_follow(user_id, username=None):
    """记录用户关注"""
    stats = get_follow_stats()
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 检查是否今天第一次重置
    if stats["last_reset_date"] != today:
        stats["today_follows"] = 0
        stats["last_reset_date"] = today
    
    # 检查用户是否已经记录过
    user_record = {
        "user_id": user_id,
        "username": username,
        "timestamp": datetime.now().isoformat()
    }
    
    # 检查是否是新用户
    existing_user = any(record["user_id"] == user_id for record in stats["follow_records"])
    if not existing_user:
        stats["total_follows"] += 1
        stats["today_follows"] += 1
        stats["follow_records"].append(user_record)
        save_follow_stats(stats)
        return True
    return False

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

async def start_handler(update: Update, context):
    payload = context.args[0] if context.args else None
    
    # 记录用户信息
    user = update.effective_user
    add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    # 移除主菜单按钮
    if payload:
        group = get_group_by_id(payload)
        if group:
            # 检查强制关注设置
            force_config = get_force_follow_config()
            if force_config["enabled"] and force_config["channel_id"]:
                user_id = update.effective_user.id
                is_member = await check_user_in_channel(context.bot, user_id, force_config["channel_id"])
                
                if not is_member:
                    # 用户未关注，显示关注提示
                    channel_link = f"https://t.me/{force_config['channel_username']}" if force_config['channel_username'] else f"https://t.me/c/{force_config['channel_id'][4:]}/1"
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("📢 关注频道", url=channel_link)],
                        [InlineKeyboardButton("🔄 重新检查", callback_data=f"check_follow_{payload}")]
                    ])
                    await update.message.reply_text(
                        f"⚠️ 请先关注频道才能获取内容！\n\n"
                        f"频道：{force_config['channel_username'] or force_config['channel_id']}\n\n"
                        f"关注后请点击下方按钮重新检查。",
                        reply_markup=keyboard
                    )
                    return
            
            # 通过检查，发送内容
            await restore_group_to_user(group, context.bot, update.effective_chat.id)
            # 自动发送确认消息
            await update.message.reply_text("✅ 内容已发送！")
        else:
            await update.message.reply_text("资源未找到或链接已失效。")
    else:
        await update.message.reply_text(
            f"欢迎！请发送任意内容，发送多条后点击下方“完成”按钮，我会帮你生成访问链接并备份到频道。\n\n{get_intro()}"
        )

async def help_handler(update: Update, context):
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

async def intro_handler(update: Update, context):
    await update.message.reply_text(get_intro())

async def setintro_handler(update: Update, context):
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

async def addadmin_handler(update: Update, context):
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

async def deladmin_handler(update: Update, context):
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

async def button_handler(update: Update, context):
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
    elif query.data.startswith("check_follow_"):
        # 处理重新检查关注状态
        payload = query.data.replace("check_follow_", "")
        group = get_group_by_id(payload)
        if group:
            force_config = get_force_follow_config()
            if force_config["enabled"] and force_config["channel_id"]:
                user_id = query.from_user.id
                is_member = await check_user_in_channel(context.bot, user_id, force_config["channel_id"])
                
                if is_member:
                    # 已关注，发送内容
                    # 记录关注统计
                    user = await context.bot.get_chat(query.from_user.id)
                    username = user.username if hasattr(user, 'username') and user.username else None
                    is_new_follow = record_follow(query.from_user.id, username)
                    
                    await restore_group_to_user(group, context.bot, query.message.chat_id)
                    await query.edit_message_text("✅ 内容已发送！")
                else:
                    # 仍未关注
                    await query.answer("❌ 您仍未关注频道，请先关注后再试！", show_alert=True)
            else:
                # 功能已关闭，直接发送
                await restore_group_to_user(group, context.bot, query.message.chat_id)
                await query.edit_message_text("✅ 内容已发送！")
        else:
            await query.edit_message_text("❌ 内容未找到或已失效！")
        await query.answer()


async def content_handler(update: Update, context):
    try:
        user_id = update.effective_user.id
        admin_ids = load_admin_ids()
        
        # 添加调试信息
        print(f"🔍 content_handler 被调用 - 用户ID: {user_id}")
        print(f"🔍 管理员列表: {admin_ids}")
        print(f"🔍 广播模式用户: {broadcast_mode_users}")
        print(f"🔍 用户是管理员: {user_id in admin_ids}")
        print(f"🔍 用户在广播模式: {user_id in broadcast_mode_users}")
        
        # 检查是否是管理员且在广播模式中
        if user_id in admin_ids and user_id in broadcast_mode_users:
            print(f"🔍 管理员在广播模式中，处理广播内容")
            # 处理广播内容
            await handle_broadcast_content(update, context)
            return
        
        print(f"🔍 content_handler 开始处理普通内容")
        
        # 记录用户信息（确保所有用户都被记录）
        user = update.effective_user
        add_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
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
    except Exception as e:
        print(f"content_handler 错误: {e}")
        # 发送错误提示给用户
        try:
            await update.message.reply_text("处理消息时出现错误，请重试。")
        except:
            pass

async def handle_broadcast_content(update: Update, context):
    """处理广播内容"""
    try:
        user_id = update.effective_user.id
        
        # 记录用户信息（确保管理员也被记录）
        user = update.effective_user
        add_user(
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        message = update.message
        media_group_id = getattr(message, 'media_group_id', None)
        
        if media_group_id:
            # 收集media group
            buf = broadcast_media_group_buffers[user_id]
            buf['media'].append(update)
            buf['last_group_id'] = media_group_id
            # 重置等待定时器
            if buf['timer']:
                buf['timer'].cancel()
            buf['timer'] = asyncio.create_task(broadcast_media_group_wait_and_confirm(user_id, context))
        else:
            # 单内容模式：直接设置广播内容
            broadcast_buffers[user_id] = [serialize_message(message)]
            
            # 获取用户数量
            users = get_users()
            
            # 显示确认界面
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ 确认发送", callback_data="confirm_broadcast")],
                [InlineKeyboardButton("❌ 取消", callback_data="cancel_broadcast")],
                [InlineKeyboardButton("📋 预览内容", callback_data="preview_broadcast")]
            ])
            
            # 根据内容类型生成预览文本
            if message.text:
                preview_text = message.text[:100] + "..." if len(message.text) > 100 else message.text
                content_type = "文本"
            elif message.photo:
                content_type = "图片"
                preview_text = "图片内容"
            elif message.video:
                content_type = "视频"
                preview_text = "视频内容"
            elif message.document:
                content_type = "文档"
                preview_text = "文档内容"
            else:
                content_type = "其他"
                preview_text = "其他类型内容"
            
            message_text = f"📢 广播确认\n\n"
            message_text += f"内容类型：{content_type}\n"
            message_text += f"内容预览：{preview_text}\n"
            message_text += f"发送给：{len(users)} 个用户\n\n"
            message_text += "⚠️ 此操作不可撤销，请确认！"
            
            await update.message.reply_text(message_text, reply_markup=keyboard)
            
            # 退出广播模式
            broadcast_mode_users.discard(user_id)
            print(f"🔍 已退出广播模式，用户ID: {user_id}")
            
    except Exception as e:
        print(f"handle_broadcast_content 错误: {e}")
        # 发送错误提示给用户
        try:
            await update.message.reply_text("处理广播内容时出现错误，请重试。")
        except:
            pass

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

async def finish_handler(update: Update, context):
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
        
        # 添加调试信息
        print(f"🔍 finish_handler - 管理员投稿，用户ID: {user_id}")
        print(f"🔍 内容数量: {len(grouped)}")
        
        try:
            # 先发送内容到频道
            await send_group_to_channel(grouped, context.bot)
            print(f"🔍 内容已发送到频道")
            
            # 生成 group_id 并存储到数据库
            from backend.utils import generate_group_id, store_group_mapping
            group_id = generate_group_id()
            print(f"🔍 生成的group_id: {group_id}")
            
            store_group_mapping(group_id, grouped)
            print(f"🔍 内容已存储到数据库")
            
            link = generate_link(group_id)
            print(f"🔍 生成的链接: {link}")
            
            # 检查链接是否有效
            if link.startswith("⚠️"):
                # 链接生成失败，只发送文本
                await context.bot.send_message(chat_id=query.message.chat_id, text=f"✅ 内容已上传到频道\n{link}")
            else:
                # 链接生成成功，发送带按钮的消息
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("点击访问内容", url=link)]
                ])
                await context.bot.send_message(chat_id=query.message.chat_id, text=f"✅ 链接已生成 👇\n{link}", reply_markup=keyboard)
            await send_link_to_backup_channels(link, context.bot)
            print(f"🔍 链接已发送给用户和备份频道")
            
        except Exception as e:
            print(f"🔍 finish_handler 错误: {e}")
            await query.edit_message_text(f"❌ 生成链接时出现错误: {str(e)}")
        
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

async def audit_handler(update: Update, context):
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

async def cancel_handler(update: Update, context):
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
    '/forcefollow': '强制关注频道管理（仅管理员）',
    '/broadcast': '广播消息和通知给所有用户（仅管理员）',
    '/qbzhiling': '显示所有机器人指令及其描述',
}

async def qbzhiling_handler(update, context):
    text = '【机器人指令列表】\n'
    for cmd, desc in COMMAND_DESCRIPTIONS.items():
        text += f'{cmd} - {desc}\n'
    await update.message.reply_text(text)

async def forcefollow_handler(update, context):
    user_id = update.effective_user.id
    admin_ids = load_admin_ids()
    if user_id not in admin_ids:
        await update.message.reply_text("无权限，仅管理员可用。")
        return
    
    if not context.args:
        await update.message.reply_text("用法：\n/forcefollow on - 开启强制关注\n/forcefollow off - 关闭强制关注\n/forcefollow set <频道ID> - 设置频道\n/forcefollow show - 显示状态\n/forcefollow stats - 查看关注统计\n/forcefollow reset - 重置统计数据")
        return
    
    action = context.args[0].lower()
    config = get_force_follow_config()
    
    if action == "on":
        if not config["channel_id"]:
            await update.message.reply_text("❌ 请先设置频道ID！\n用法：/forcefollow set <频道ID>")
            return
        config["enabled"] = True
        save_force_follow_config(config)
        await update.message.reply_text("✅ 强制关注功能已开启！")
        
    elif action == "off":
        config["enabled"] = False
        save_force_follow_config(config)
        await update.message.reply_text("✅ 强制关注功能已关闭！")
        
    elif action == "set":
        if len(context.args) < 2:
            await update.message.reply_text("用法：/forcefollow set <频道ID>\n如：/forcefollow set -100xxxxxxxxxx")
            return
        
        channel_id = context.args[1]
        if not channel_id.startswith('-100'):
            await update.message.reply_text("❌ 频道ID必须以 -100 开头！")
            return
        
        # 尝试获取频道信息
        try:
            chat = await context.bot.get_chat(channel_id)
            config["channel_id"] = channel_id
            config["channel_username"] = chat.username or ""
            save_force_follow_config(config)
            await update.message.reply_text(f"✅ 强制关注频道已设置：\n频道：{chat.title}\nID：{channel_id}")
        except Exception as e:
            await update.message.reply_text(f"❌ 设置失败：{str(e)}\n请确保机器人是频道管理员！")
            
    elif action == "show":
        status = "开启" if config["enabled"] else "关闭"
        channel_info = f"{config['channel_username']} ({config['channel_id']})" if config["channel_id"] else "未设置"
        await update.message.reply_text(f"📊 强制关注设置状态：\n\n状态：{status}\n频道：{channel_info}")
        
    elif action == "stats":
        stats = get_follow_stats()
        await update.message.reply_text(
            f"📈 关注统计报告\n\n"
            f"总关注人数：{stats['total_follows']} 人\n"
            f"今日关注：{stats['today_follows']} 人\n"
            f"最后更新：{stats['last_reset_date'] or '无数据'}\n\n"
            f"💡 统计说明：\n"
            f"• 只统计通过强制关注检查的用户\n"
            f"• 每个用户只统计一次\n"
            f"• 每日自动重置今日数据"
        )
        
    elif action == "reset":
        stats = get_follow_stats()
        stats["total_follows"] = 0
        stats["today_follows"] = 0
        stats["follow_records"] = []
        stats["last_reset_date"] = ""
        save_follow_stats(stats)
        await update.message.reply_text("✅ 统计数据已重置！")
        
    else:
        await update.message.reply_text("用法：\n/forcefollow on - 开启强制关注\n/forcefollow off - 关闭强制关注\n/forcefollow set <频道ID> - 设置频道\n/forcefollow show - 显示状态\n/forcefollow stats - 查看关注统计\n/forcefollow reset - 重置统计数据")

# 广播功能
async def broadcast_handler(update: Update, context):
    """广播消息给所有用户"""
    user_id = update.effective_user.id
    admin_ids = load_admin_ids()
    if user_id not in admin_ids:
        await update.message.reply_text("无权限，仅管理员可用。")
        return
    
    if not context.args:
        help_text = """📢 广播功能使用说明：

【快捷指令】
/broadcast <内容> - 直接发送文本广播
/broadcast start - 开始广播模式（单内容）

【管理指令】
/broadcast stats - 查看用户统计
/broadcast history - 查看广播历史
/broadcast status - 查看当前状态

【通知指令】
/broadcast notify <内容> - 发送系统通知

💡 提示：直接发送 /broadcast 内容 即可快速广播"""
        await update.message.reply_text(help_text)
        return
    
    action = context.args[0].lower()
    
    if action == "start":
        # 开始广播模式
        print(f"🔍 执行 /broadcast start - 用户ID: {user_id}")
        print(f"🔍 广播模式用户 (之前): {broadcast_mode_users}")
        broadcast_mode_users.add(user_id)  # 添加用户到广播模式
        print(f"🔍 广播模式用户 (之后): {broadcast_mode_users}")
        
        await update.message.reply_text(
            "📢 广播模式已开启！\n\n"
            "请发送要广播的内容（支持文本、图片、视频等），"
            "发送后会自动显示确认界面。\n\n"
            "💡 提示：发送 /broadcast status 可查看当前状态"
        )
    elif action == "stats":
        # 显示用户统计
        users = get_users()
        total_users = len(users)
        active_users = len([u for u in users if u.get('last_active')])
        await update.message.reply_text(
            f"📊 用户统计：\n\n"
            f"总用户数：{total_users} 人\n"
            f"活跃用户：{active_users} 人\n"
            f"今日新增：{len([u for u in users if u.get('joined_at', '').startswith(datetime.now().strftime('%Y-%m-%d'))])} 人"
        )
    elif action == "history":
        # 显示广播历史
        history = get_broadcast_history()
        if not history:
            await update.message.reply_text("📝 暂无广播历史记录。")
            return
        
        text = "📝 最近广播历史：\n\n"
        for i, record in enumerate(history[-10:], 1):  # 显示最近10条
            timestamp = record['timestamp'][:19].replace('T', ' ')  # 格式化时间
            text += f"{i}. {timestamp} - 发送给 {record['total_users']} 人，成功 {record['success_count']} 人\n"
        await update.message.reply_text(text)
    elif action == "status":
        # 显示广播状态
        is_in_broadcast_mode = user_id in broadcast_mode_users
        users = get_users()
        
        status_text = "📢 广播状态：\n\n"
        if is_in_broadcast_mode:
            status_text += "🟢 当前状态：广播模式已开启\n"
            status_text += f"👥 目标用户：{len(users)} 人\n"
            status_text += "💡 请发送要广播的内容"
        else:
            status_text += "🔴 当前状态：普通模式\n"
            status_text += f"👥 总用户数：{len(users)} 人\n"
            status_text += "💡 发送 /broadcast start 开始广播模式"
        
        await update.message.reply_text(status_text)
    elif action == "notify":
        # 发送广播通知
        if not context.args or len(context.args) < 2:
            await update.message.reply_text("用法：/broadcast notify <通知内容>\n例如：/broadcast notify 系统维护通知")
            return
        
        notification_text = ' '.join(context.args[1:])
        users = get_users()
        
        if not users:
            await update.message.reply_text("❌ 没有用户可发送通知。")
            return
        
        # 缓存通知内容
        notification_cache[user_id] = notification_text
        
        # 确认发送通知
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ 确认发送通知", callback_data="send_notification")],
            [InlineKeyboardButton("❌ 取消", callback_data="cancel_notification")]
        ])
        
        await update.message.reply_text(
            f"📢 确认发送通知\n\n"
            f"通知内容：{notification_text}\n"
            f"发送给：{len(users)} 个用户\n\n"
            f"⚠️ 此操作不可撤销，请确认！",
            reply_markup=keyboard
        )
    else:
        # 直接发送文本广播（新功能）
        text_content = ' '.join(context.args)
        users = get_users()
        
        if not users:
            await update.message.reply_text("❌ 没有用户可发送广播。")
            return
        
        # 将文本内容添加到广播缓冲区
        broadcast_buffers[user_id] = [{'type': 'text', 'text': text_content}]
        
        # 直接发送确认
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ 立即发送", callback_data="confirm_broadcast")],
            [InlineKeyboardButton("❌ 取消", callback_data="cancel_broadcast")]
        ])
        
        await update.message.reply_text(
            f"📢 快速广播\n\n"
            f"内容：{text_content}\n"
            f"发送给：{len(users)} 个用户\n\n"
            f"⚠️ 此操作不可撤销，请确认！",
            reply_markup=keyboard
        )



async def broadcast_media_group_wait_and_confirm(user_id, context):
    """等待媒体组完成并确认"""
    await asyncio.sleep(2.5)  # 等待2.5秒
    buf = broadcast_media_group_buffers[user_id]
    
    # 处理媒体组
    if buf['media']:
        media_group_id = buf['last_group_id']
        group_items = []
        for update in buf['media']:
            message = update.message
            group_items.append(serialize_message(message))
        
        # 单内容模式：直接设置广播内容
        broadcast_buffers[user_id] = [{'type': 'media_group', 'items': group_items}]
        buf['media'].clear()
        buf['timer'] = None
        
        # 获取用户数量
        users = get_users()
        
        # 显示确认界面
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ 确认发送", callback_data="confirm_broadcast")],
            [InlineKeyboardButton("❌ 取消", callback_data="cancel_broadcast")],
            [InlineKeyboardButton("📋 预览内容", callback_data="preview_broadcast")]
        ])
        
        message_text = f"📢 广播确认\n\n"
        message_text += f"内容类型：媒体组\n"
        message_text += f"内容数量：{len(group_items)} 个文件\n"
        message_text += f"发送给：{len(users)} 个用户\n\n"
        message_text += "⚠️ 此操作不可撤销，请确认！"
        
        await context.bot.send_message(
            chat_id=user_id,
            text=message_text,
            reply_markup=keyboard
        )
        
        # 退出广播模式
        broadcast_mode_users.discard(user_id)
        print(f"🔍 已退出广播模式，用户ID: {user_id}")

async def broadcast_callback_handler(update: Update, context):
    """处理广播相关的回调"""
    query = update.callback_query
    user_id = query.from_user.id
    admin_ids = load_admin_ids()
    
    if user_id not in admin_ids:
        await query.answer("无权限，仅管理员可用。", show_alert=True)
        return
    
    if query.data == "confirm_broadcast":
        # 确认发送广播
        buffer = broadcast_buffers.get(user_id, [])
        if not buffer:
            await query.answer("❌ 没有待广播的内容！", show_alert=True)
            return
        
        users = get_users()
        if not users:
            await query.answer("❌ 没有用户可发送广播！", show_alert=True)
            return
        
        await query.edit_message_text("📤 正在发送广播，请稍候...")
        
        success_count = 0
        failed_count = 0
        failed_users = []
        
        for user_info in users:
            try:
                user_id_target = user_info["user_id"]
                # 发送内容给用户
                for item in buffer:
                    await send_item_to_chat(item, context.bot, user_id_target)
                success_count += 1
                await asyncio.sleep(0.1)  # 避免频率限制
            except Exception as e:
                failed_count += 1
                failed_users.append(str(user_id_target))
                print(f"发送广播给用户 {user_id_target} 失败: {e}")
        
        # 保存广播历史
        broadcast_info = {
            "timestamp": datetime.now().isoformat(),
            "admin_id": user_id,
            "type": "broadcast",
            "total_users": len(users),
            "success_count": success_count,
            "failed_count": failed_count
        }
        save_broadcast_history(broadcast_info)
        
        # 清空广播缓冲区
        broadcast_buffers[user_id].clear()
        
        result_text = (
            f"✅ 广播发送完成！\n\n"
            f"📊 发送统计：\n"
            f"• 总用户数：{len(users)} 人\n"
            f"• 发送成功：{success_count} 人\n"
            f"• 发送失败：{failed_count} 人\n"
            f"• 成功率：{success_count/len(users)*100:.1f}%"
        )
        
        if failed_users:
            result_text += f"\n\n❌ 失败用户（前10个）：\n" + "\n".join(failed_users[:10])
        
        await query.edit_message_text(result_text)
    
    elif query.data == "cancel_broadcast":
        # 取消广播
        broadcast_buffers[user_id].clear()
        broadcast_media_group_buffers[user_id]['media'].clear()
        if broadcast_media_group_buffers[user_id]['timer']:
            broadcast_media_group_buffers[user_id]['timer'].cancel()
            broadcast_media_group_buffers[user_id]['timer'] = None
        await query.edit_message_text("❌ 广播已取消。")
    
    elif query.data == "preview_broadcast":
        # 预览广播内容
        buffer = broadcast_buffers.get(user_id, [])
        if not buffer:
            await query.answer("❌ 没有待广播的内容！", show_alert=True)
            return
        
        await query.edit_message_text("📋 正在生成预览...")
        
        # 发送预览内容
        for i, item in enumerate(buffer, 1):
            await send_item_to_chat(item, context.bot, query.message.chat_id, prefix=f"[预览 {i}] ")
        
        # 恢复原消息
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ 确认发送", callback_data="confirm_broadcast")],
            [InlineKeyboardButton("❌ 取消", callback_data="cancel_broadcast")],
            [InlineKeyboardButton("📋 预览内容", callback_data="preview_broadcast")]
        ])
        
        await query.edit_message_text(
            f"📢 广播确认\n\n"
            f"内容已预览完成，请确认是否发送。",
            reply_markup=keyboard
        )
    
    elif query.data == "send_notification":
        # 发送通知
        users = get_users()
        
        if not users:
            await query.answer("❌ 没有用户可发送通知！", show_alert=True)
            return
        
        # 从缓存中获取通知内容
        notification_text = notification_cache.get(user_id, "📢 系统通知\n\n这是一条来自管理员的系统通知。")
        
        # 格式化通知内容
        formatted_notification = f"📢 <b>系统通知</b>\n\n{notification_text}\n\n<i>来自管理员</i>"
        
        await query.edit_message_text("📤 正在发送通知，请稍候...")
        
        success_count = 0
        failed_count = 0
        
        for user_info in users:
            try:
                user_id_target = user_info["user_id"]
                await context.bot.send_message(
                    chat_id=user_id_target,
                    text=formatted_notification,
                    parse_mode='HTML'
                )
                success_count += 1
                await asyncio.sleep(0.1)
            except Exception as e:
                failed_count += 1
                print(f"发送通知给用户 {user_id_target} 失败: {e}")
        
        # 保存通知历史
        notification_info = {
            "timestamp": datetime.now().isoformat(),
            "admin_id": user_id,
            "type": "notification",
            "total_users": len(users),
            "success_count": success_count,
            "failed_count": failed_count
        }
        save_broadcast_history(notification_info)
        
        result_text = (
            f"✅ 系统通知发送完成！\n\n"
            f"📊 发送统计：\n"
            f"• 总用户数：{len(users)} 人\n"
            f"• 发送成功：{success_count} 人\n"
            f"• 发送失败：{failed_count} 人\n"
            f"• 成功率：{success_count/len(users)*100:.1f}%"
        )
        
        await query.edit_message_text(result_text)
    
    elif query.data == "cancel_notification":
        await query.edit_message_text("❌ 通知发送已取消。")
    
    await query.answer()

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
    application.add_handler(CommandHandler("forcefollow", forcefollow_handler))
    application.add_handler(CommandHandler("broadcast", broadcast_handler))
    application.add_handler(CommandHandler("qbzhiling", qbzhiling_handler))
    
    # 使用单个MessageHandler处理所有消息
    application.add_handler(MessageHandler(filters.ALL, content_handler))
    
    application.add_handler(CallbackQueryHandler(finish_handler, pattern="^finish$"))
    application.add_handler(CallbackQueryHandler(audit_handler, pattern="^(approve_|reject_).*$"))
    application.add_handler(CallbackQueryHandler(cancel_handler, pattern="^cancel$"))
    application.add_handler(CallbackQueryHandler(button_handler, pattern="^(help|start|admin_manage|check_follow_).*$"))
    application.add_handler(CallbackQueryHandler(broadcast_callback_handler, pattern="^(confirm_broadcast|cancel_broadcast|preview_broadcast|send_notification|cancel_notification)$")) 
