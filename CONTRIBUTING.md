# 贡献指南

感谢你对本项目的关注！

## 开发环境搭建

```bash
# 克隆仓库
git clone <repo-url>
cd daily-info-push

# 安装依赖（需要 uv）
uv sync

# 配置环境变量
mkdir -p ~/.daily-info-push
cp .env.example ~/.daily-info-push/.env
# 填入你的 API key
```

## 添加新的 Adapter

Adapter 位于 `adapters/` 目录，每个 adapter 负责从单一数据源抓取数据。

1. 在 `adapters/` 下新建文件（如 `adapters/my_source.py`）
2. 参照已有 adapter 的模式实现
3. 在 fetcher 流程中注册新 adapter
4. 用 dry run 测试：`uv run python main.py --dry-run --date $(date +%F)`

## Pull Request 流程

1. Fork 仓库并创建功能分支
2. 完成修改
3. 本地使用 `--dry-run` 验证流程正常
4. 提交 PR，清晰描述改动内容和原因

## 代码风格

- Python 3.12+
- 适当使用类型注解
- 保持 adapter 自包含——每个 adapter 自行处理 HTTP 请求和数据解析

## 问题反馈

在 GitHub 提 issue，请包含：
- 期望行为
- 实际行为
- 复现步骤（如适用）
