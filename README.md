# tg-nrcc 资源管理机器人（超详细小白部署版）

## 项目简介
这是一个开箱即用的 Telegram 资源管理机器人，支持内容投稿、合并、频道备份、管理员审核。适合个人/团队/社群资源管理。

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

### 5. 测试启动机器人
```bash
python3 -m bot.main
```
- 看到“Polling started”或无报错即为成功。

### 6. 配置 systemd 后台守护（可选但推荐）
1. 新建服务文件 `/etc/systemd/system/tg-nrcc-bot.service`，内容如下（请根据实际路径和用户名修改）：
    ```ini
    [Unit]
    Description=Telegram NRCC Bot
    After=network.target

    [Service]
    Type=simple
    WorkingDirectory=/root/tg-nrcc/tg-nrcc-backup
    ExecStart=/usr/bin/python3 -m bot.main
    Restart=always
    User=root
    Environment=PYTHONUNBUFFERED=1
    Environment=PYTHONPATH=/root/tg-nrcc/tg-nrcc-backup

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

---

## 贡献与支持
如有问题请提交 issue 或联系开发者。

---

## 祝你部署顺利！ 
