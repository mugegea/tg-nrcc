# tg-nrcc 资源管理机器人（超详细小白部署版）

## 项目简介

这是一个开箱即用的 Telegram 资源管理机器人，支持内容投稿、合并、频道备份、管理员审核、强制关注等功能。适合个人/团队/社群资源管理。

---

## 功能特性

- ✅ 支持任意内容（文本、图片、视频等）发送给机器人，生成唯一访问链接
- ✅ 多条内容可合并为一个链接，点击"完成"后生成
- ✅ 所有内容自动备份到绑定频道
- ✅ 支持多个绑定频道和备用频道
- ✅ 管理员可审核普通用户投稿
- ✅ 强制关注功能：要求用户关注指定频道才能获取内容
- ✅ 支持 systemd 部署
- ✅ 支持频道/管理员动态管理

---

## 机器人指令列表

| 指令 | 说明 |
|------|------|
| /start [参数] | 获取资源或显示欢迎信息 |
| /help | 显示帮助和功能说明 |
| /intro | 查看机器人介绍 |
| /setintro <内容> | 设置机器人介绍（仅管理员） |
| /addadmin <用户ID> | 添加管理员（仅管理员） |
| /deladmin <用户ID> | 删除管理员（仅管理员） |
| /addchannel <频道ID> | 添加绑定频道（仅管理员） |
| /rmchannel <频道ID> | 移除绑定频道（仅管理员） |
| /listchannels | 列出所有绑定频道 |
| /addbackupchannel <频道ID> | 添加备用频道（仅管理员） |
| /rmbackupchannel <频道ID> | 移除备用频道（仅管理员） |
| /listbackupchannels | 列出所有备用频道 |
| /forcefollow on | 开启强制关注功能（仅管理员） |
| /forcefollow off | 关闭强制关注功能（仅管理员） |
| /forcefollow set <频道ID> | 设置需要关注的频道（仅管理员） |
| /forcefollow show | 显示强制关注设置状态（仅管理员） |
| /qbzhiling | 显示所有机器人指令及其描述 |

> 说明：
> - 绑定频道用于内容备份，支持多个。
> - 备用频道仅用于推送生成的链接，也支持多个。
> - 强制关注功能可以要求用户关注指定频道才能获取内容。
> - 管理员相关指令仅管理员可用。
> - 普通用户投稿需管理员审核后才会生成链接。

---

## 一键部署流程（适合完全没有经验的小白）

### 1. 购买并连接 VPS

- 推荐 Ubuntu 20.04/22.04 系统。
- 用 Xshell、MobaXterm、macOS/Linux 终端等 SSH 工具连接你的 VPS。

### 2. 下载并进入项目目录

```bash
git clone https://github.com/mugegea/tg-nrcc.git
cd tg-nrcc
```

### 3. 运行一键安装脚本

```bash
bash install.sh
```

- 脚本会自动安装 Python3、pip3、git、依赖包，并初始化 storage 目录。

### 4. 配置环境变量

- 复制 `.env.example` 为 `.env`：
  ```bash
  cp .env.example .env
  ```
- 用 `nano .env` 或 `vim .env` 编辑，填写你的 Bot Token、频道ID、Bot用户名。
  - `BOT_TOKEN`：在 [@BotFather](https://t.me/BotFather) 创建机器人后获得。
  - `CHANNEL_ID`：你的频道ID，必须以 `-100` 开头，可用 [@userinfobot](https://t.me/userinfobot) 查询。
  - `BOT_USERNAME`：你的机器人用户名，不带 @。

### 5. 设置管理员

```bash
nano storage/admin_ids.json
```

将你的 Telegram ID 添加到数组中：
```json
[你的Telegram数字ID]
```

### 6. 测试启动机器人

```bash
python3 -m bot.main
```

- 看到"Polling started"或无报错即为成功。

### 7. 配置 systemd 后台守护（可选但推荐）

1. 新建服务文件 `/etc/systemd/system/tg-nrcc-bot.service`，内容如下（请根据实际路径和用户名修改）：
    ```ini
    [Unit]
    Description=Telegram NRCC Bot
    After=network.target

    [Service]
    Type=simple
    WorkingDirectory=/root/tg-nrcc
    ExecStart=/usr/bin/python3 -m bot.main
    Restart=always
    User=root
    Environment=PYTHONUNBUFFERED=1
    Environment=PYTHONPATH=/root/tg-nrcc

    [Install]
    WantedBy=multi-user.target
    ```
2. 启用并启动服务：
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable tg-nrcc-bot
    sudo systemctl start tg-nrcc-bot
    ```
3. 查看日志：
    ```bash
    sudo journalctl -u tg-nrcc-bot -f
    ```

---

## 目录结构说明

- bot/         机器人主逻辑
- backend/     工具与数据库操作
- storage/     数据库存储与配置文件
- requirements.txt  依赖列表
- .env.example 环境变量模板
- install.sh   一键部署脚本
- test_env.py  环境变量测试脚本

### storage/ 目录说明

- admin_ids.json         管理员ID列表
- bind_channels.json     绑定频道ID列表
- backup_channels.json   备用频道ID列表
- bind_channel.txt       单频道绑定（兼容老逻辑）
- intro.txt              机器人介绍文本
- force_follow.json      强制关注功能配置
- mapping.db             内容映射数据库（自动生成）

---

## 强制关注功能使用

### 开启强制关注

1. **设置目标频道**：
   ```bash
   /forcefollow set -100xxxxxxxxxx
   ```

2. **开启功能**：
   ```bash
   /forcefollow on
   ```

3. **查看状态**：
   ```bash
   /forcefollow show
   ```

### 注意事项

- 机器人必须是目标频道的管理员
- 频道ID必须以 `-100` 开头
- 功能默认关闭，需要手动开启

---

## 常见问题与解决办法

- **启动报错 `No module named 'bot'`**  
  用 `python3 -m bot.main` 启动，或检查 systemd 配置路径。

- **.env 文件无效**  
  必须在项目根目录，内容格式正确。

- **频道ID必须以 `-100` 开头**  
  用 [@userinfobot](https://t.me/userinfobot) 查询。

- **如何升级/重装**  
  直接覆盖文件，重新运行 `install.sh`，再重启 systemd 服务即可。

- **强制关注功能不工作**  
  确保机器人是目标频道的管理员，并且频道ID格式正确。

---

## 服务管理命令

```bash
# 查看状态
sudo systemctl status tg-nrcc-bot

# 重启服务
sudo systemctl restart tg-nrcc-bot

# 停止服务
sudo systemctl stop tg-nrcc-bot

# 查看日志
sudo journalctl -u tg-nrcc-bot -f
```

---

## 贡献与支持

如有问题请提交 issue 或联系开发者。

---

## 祝你部署顺利！ 
