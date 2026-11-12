# 配置与本地定时运行

配置为 JSON，独立于 skill checkout，路径 `~/.config/keep-me-update/config.json`。`config.example.json` 提供字段示例。旧版本的 `user_config.yaml` 可以作为迁移信息，但当前脚本不会读取 YAML，迁移时按用户原设置写入 JSON。

- `timezone`：IANA 时区，默认 Asia/Shanghai。
- `delivery_time`：HH:MM，默认 08:00。修改后重新运行安装器更新 cron。
- `output_dir`：本地报纸目录。
- `lookback_hours`：新闻发布时间窗口，默认36小时。
- `articles_per_feed`：每源候选上限，默认18。
- `feeds_path`：可选，自定义源 JSON；省略则用 `scripts/newspaper_feeds.default.json`。结构为 `[{"title":"来源名","url":"https://…/rss","category":"world","enabled":true}]`。
- `codex_bin`：可选，Codex CLI 的绝对路径，安装器自动解析。
- `model_timeout_seconds`：编辑调用超时，默认600秒。
- `desktop_notification`：是否通过 notify-send 通知。
- `proxy_url`：可选，本机代理地址。供 cron 的采集和 Codex 连接使用；含认证信息时只存本机配置。

```bash
cp config.example.json /tmp/my-news-config.json
# 编辑 output_dir 等字段
python3 scripts/install_local.py --config /tmp/my-news-config.json --dry-run
python3 scripts/install_local.py --config /tmp/my-news-config.json
python3 scripts/daily_report.py
```

`--collect-only` 仅采集来源证据；`--force` 重做当天成功报纸；`--catch-up` 在早于交付时间时跳过。

cron 网络需要代理时配置 `proxy_url`，不把凭据提交到仓库。桌面通知连接当前用户的 D-Bus 会话，未登录桌面时文件仍会生成。模型编辑需有效的 Codex 登录和可用额度。

安装器备份初始 crontab 至配置目录，更新有标记的任务，保留其他任务。查看 `crontab -l` 与输出目录的 `cron.log`。停用时只删除 `BEGIN keep-me-update` 至 `END keep-me-update` 标记内的块，保留其余 crontab。
