#!/bin/bash
set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

print_info "==== Telegram NRCC Bot 一键部署脚本 ===="

# 检查是否在 tg-nrcc-backup 目录
if [ ! -f install.sh ] || [ ! -d bot ] || [ ! -d backend ]; then
  print_error "请先进入 tg-nrcc-backup 目录再运行本脚本！"
  exit 1
fi

# 1. 安装依赖
print_info "安装 Python3、pip3、git..."
sudo apt update
sudo apt install -y python3 python3-pip git

# 2. 检查 requirements.txt
if [ ! -f requirements.txt ]; then
  print_error "未找到 requirements.txt，请确认你在 tg-nrcc-backup 目录下！"
  exit 1
fi

# 3. 安装 Python 依赖
print_info "安装 Python 依赖..."
pip3 install -r requirements.txt

# 4. 初始化 storage 目录
print_info "初始化 storage 目录..."
mkdir -p storage
touch storage/admin_ids.json storage/bind_channels.json storage/backup_channels.json storage/bind_channel.txt storage/intro.txt storage/force_follow.json storage/follow_stats.json storage/users.json storage/broadcast_history.json
echo "[]" > storage/admin_ids.json
echo "[]" > storage/bind_channels.json
echo "[]" > storage/backup_channels.json
echo "" > storage/bind_channel.txt
echo "这是一个资源管理机器人，支持任意内容合并分享。" > storage/intro.txt
echo '{"enabled": false, "channel_id": "", "channel_username": ""}' > storage/force_follow.json
echo '{"total_follows": 0, "today_follows": 0, "last_reset_date": "", "follow_records": []}' > storage/follow_stats.json
echo "[]" > storage/users.json
echo "[]" > storage/broadcast_history.json

print_success "storage 目录初始化完成！"
print_info "已创建广播功能所需的用户数据库和广播历史文件"

# 5. 引导用户配置 .env
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    print_info "复制 .env.example 为 .env ..."
    cp .env.example .env
    print_success ".env 文件已生成，请用 nano .env 编辑你的 Token、频道ID、Bot用户名。"
  else
    print_error "未找到 .env.example，请手动创建 .env 文件！"
    exit 1
  fi
else
  print_info ".env 已存在，请确认内容无误。"
fi

print_success "==== 部署完成！下一步：请编辑 .env 文件，然后用 python3 -m bot.main 测试运行 ===="
print_info "💡 新功能提示：机器人现在支持广播功能，管理员可以使用 /broadcast 命令向所有用户发送消息"
print_info "📖 详细使用说明请查看 BROADCAST_README.md 文件" 
