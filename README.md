# Storage 目录说明

此目录包含机器人的配置和数据文件，由 `install.sh` 脚本自动创建。

## 文件说明

- `admin_ids.json` - 管理员ID列表
- `bind_channels.json` - 绑定频道ID列表  
- `backup_channels.json` - 备用频道ID列表
- `bind_channel.txt` - 单频道绑定（兼容老逻辑）
- `intro.txt` - 机器人介绍文本
- `force_follow.json` - 强制关注功能配置
- `follow_stats.json` - 关注统计数据
- `mapping.db` - 内容映射数据库（自动生成）

## 初始化

运行 `bash install.sh` 会自动创建这些文件并设置默认值。

## 注意事项

- 这些文件包含敏感配置，不要公开分享
- 数据库文件会自动生成，无需手动创建
- 修改配置后需要重启机器人服务 
