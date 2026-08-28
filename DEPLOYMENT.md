# 部署信息

- 平台：AWS Lightsail（Ubuntu）
- 时区：`Asia/Shanghai`
- SSH 别名：`daily-info-push`
- 项目目录：`/home/ubuntu/daily-info-push`
- 远程仓库：`git@github.com:codefishx/daily-info-push.git`

具体主机地址和密钥信息保存在本机的 `DEPLOYMENT.local.md`，不纳入版本控制。

## 连接与更新

```bash
ssh daily-info-push
cd /home/ubuntu/daily-info-push
git pull --ff-only origin master
```

## 定时推送

服务器使用北京时间，每天 `08:00` 推送一次：

```cron
PATH=/usr/local/bin:/usr/bin:/bin:/home/ubuntu/.local/bin:/home/ubuntu/.cargo/bin
0 8 * * * /home/ubuntu/daily-info-push/run.sh morning
```

查看配置与日志：

```bash
crontab -l
tail -n 100 ~/.daily-info-push/logs/$(date +%F)_morning.log
```
