# Zotero-Arxiv-Feishu-LLM

<p align="center">
  <img src="docs/teaser.png" width="80%">
</p>

从 arXiv 获取当天的新论文，基于嵌入相似度匹配你的 Zotero 库（作为兴趣集），用 LLM 生成 TLDR/翻译，并通过飞书卡片或企业微信 Markdown 消息推送。默认只有最小链路，去掉了邮件、复杂 CI 等附加流程。

## 功能概览
- 拉取当天 arXiv 新稿，按指定学科/关键词过滤。
- 从 Zotero 库读取标题/摘要/作者/标签等，作为兴趣参考。
- 使用句向量模型计算相似度，截取最相关的论文。
- 可选生成中文 TLDR、摘要翻译；评分星级一并展示。
- 通过飞书自定义机器人推送卡片或企业微信机器人推送 Markdown 消息，预览前 N 篇，便于快速浏览。

## 工作流程
1) 读取 Zotero 库（忽略没有摘要的条目），保留元信息。  
2) 拉取当天 arXiv 新稿（按 `arxiv.query`）。  
3) 计算 arXiv ↔ Zotero 摘要的相似度，按分数排序并截取 `query.max_results`。  
4) 可选生成 TLDR、摘要翻译；添加相关度星级。  
5) 通过飞书 Webhook 发送互动卡片或企业微信 Webhook 发送 Markdown 消息，含标题/链接、作者、关键词、TLDR/摘要预览。

## 环境要求
- Python 3.10+。
- 可访问任意 OpenAI 兼容接口（官方或自建均可）。
- 准备好 Zotero 的 Library ID 与 API Key，以及飞书机器人的 Webhook 或企业微信机器人的 Webhook。
- 默认只需 CPU；嵌入与 LLM 请求都走远端 API。

## 快速开始
1. 安装依赖：`pip install -r requirements.txt`
2. 复制配置模板：`cp config.example.yaml config.yaml`
3. 在 `config.yaml` 填写自己的信息，或用环境变量覆盖敏感字段（推荐）；详见下文。
4. 运行：`python main.py`（默认读取当天新稿并推送到 Webhook）
5. 想先演练不打扰正式群，可设置 `FEISHU_TEST_WEBHOOK` 临时接收。

## Zotero配置
- 在 Zotero 网页端：Settings → Feeds/API → 创建 Private Key，勾选 Library 访问权限；记录生成的 API Key。
- Library ID 获取方式：个人库在 Feeds/API 页面可见 UserID；群组库在 `https://www.zotero.org/groups/<group_id>` 的数字即 Group ID。
- 在 `config.yaml` 填写 `zotero.library_id`、`zotero.api_key`、`zotero.library_type`（`user` 或 `group`）；可调整 `item_types`（如增加 `book`、`thesis`）和 `max_items` 以加速大库。
- 如果部分条目缺摘要，会被自动忽略；建议在 Zotero 里尽量补全摘要以提升匹配质量。

## OpenAI Style API
- LLM 调用使用 OpenAI 兼容接口（chat/completions），默认以 `response_format={"type": "json_object"}` 获取结构化输出。
- 在 `config.yaml` 设置 `llm.base_url`、`llm.model`、`llm.api_key`（或用环境变量 `LLM_BASE_URL` / `LLM_MODEL` / `LLM_API_KEY`），可指向官方 OpenAI、Azure OpenAI、自建兼容网关或本地服务。
- 确认所选模型支持 JSON 输出；若不支持，请更换模型或关闭依赖 LLM 的功能（如 TLDR/翻译）。
- 可同时配置 `OPENAI_API_KEY`/`OPENAI_BASE_URL`/`OPENAI_MODEL`，与 `LLM_*` 等价，方便复用已有环境变量。


## 飞书配置
- 在飞书群添加「自定义机器人」，复制生成的 Webhook（参考 [官方指南](https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot)）。
- 本项目直接用 Webhook 发送卡片，无需额外模板；如需自定义样式，可调整 `feishu.header_template`、`feishu.title` 等配置。

## 企业微信配置
- 在企业微信群聊中添加「自定义机器人」（群机器人），复制生成的 Webhook URL（参考 [官方文档](https://developer.work.weixin.qq.com/document/path/91770)）。
- 消息以 Markdown 格式通过 Webhook 发送；在 `config.yaml` 中配置 `wechat.webhook_url` / `wechat.title`。
- **消息长度**：由于企业微信单条消息限制为 4096 字符，程序会自动将内容按 1000 字符分割成多条消息发送。
- **优先级**：如果同时配置了飞书和企业微信，程序会优先使用企业微信。

## 密钥与环境变量
敏感字段可通过环境变量注入（CI/容器推荐），优先级：环境变量 > `config.yaml` > `config.example.yaml`。

| 名称 | 必填 | 来源 | 说明 |
| --- | --- | --- | --- |
| `FEISHU_WEBHOOK` | 否* | Secrets / 环境变量 | `LARK_WEBHOOK` 也可；测试用 `FEISHU_TEST_WEBHOOK`。*未配置企业微信时必填。 |
| `WECHAT_WEBHOOK` | 否* | Secrets / 环境变量 | `WECHAT_WORK_WEBHOOK` 也可；测试用 `WECHAT_TEST_WEBHOOK`。*未配置飞书时必填。 |
| `ZOTERO_ID` | 是 | Secrets / 环境变量 | Zotero 库 ID。 |
| `ZOTERO_KEY` | 是 | Secrets / 环境变量 | Zotero API Key。 |
| `ZOTERO_LIBRARY_TYPE` | 是 | Secrets / 环境变量 | `user` 或 `group`。 |
| `LLM_API_KEY` | 是 | Secrets / 环境变量 | OpenAI 兼容 API Key。 |
| `LLM_MODEL` | 是 | Secrets / 环境变量 | 模型名。 |
| `LLM_BASE_URL` | 是 | Secrets / 环境变量 | 使用官方 OpenAI 可填默认。 |
| `OPENAI_API_KEY` | 否 | Secrets / 环境变量 | `LLM_API_KEY` 别名。 |
| `OPENAI_MODEL` | 否 | Secrets / 环境变量 | `LLM_MODEL` 别名。 |
| `OPENAI_BASE_URL` | 否 | Secrets / 环境变量 | `LLM_BASE_URL` 别名。 |

## GitHub Actions
工作流 `.github/workflows/run.yml`：
- `run` Job：仅定时触发（使用飞书）。
- `test` Job：仅手动触发，使用 `FEISHU_TEST_WEBHOOK`，便于演练不打扰正式群。

工作流 `.github/workflows/run_ep_wechat.yml`：
- `run` Job：仅定时触发（使用企业微信）。
- `test` Job：仅手动触发，使用 `WECHAT_TEST_WEBHOOK`，便于演练不打扰正式群。

- 在仓库 Settings → Secrets 添加上述环境变量后，即可点击 "Run workflow" 触发；工作流会自动复制 `config.example.yaml` 为 `config.yaml` 并执行 `python main.py`。
- 想无本地部署、直接在 GitHub 上用：Fork 仓库 → 在自己 Fork 的 Settings → Secrets 配好变量（同上）→ 打开 Actions 选项卡，手动触发 `run` 或 `test` 工作流即可，无需本地 clone；后续可在 Fork 里改 `config.example.yaml` / `arxiv.query` 等参数，再次运行。

## 配置项速览（`config.yaml`）
- `feishu.webhook_url`：飞书机器人 Webhook。
- `feishu.title` / `feishu.header_template`：卡片标题与头部色（blue / wathet / turquoise / green / yellow / orange / red / carmine；填 `#DAE3FA` 会自动映射为 wathet）。
- `wechat.webhook_url`：企业微信机器人 Webhook。
- `wechat.title`：企业微信消息标题。
- `arxiv.source`（`rss` 或 `api`）、`arxiv.query` / `arxiv.max_results` / `arxiv.days_back`（支持小数天数表示小时） ：arXiv 拉取方式与时间窗口。
- `arxiv.rss_wait_minutes` / `arxiv.rss_retry_minutes`：使用 RSS 时若暂无更新则轮询等待（例如日更未发布时）。
- 定时规则：`on.schedule` 的 cron 只负责触发排队。
- `zotero.library_id` / `zotero.api_key` / `zotero.library_type` / `zotero.item_types` / `zotero.max_items`：Zotero 访问与过滤。
- `embedding.model`：相似度嵌入模型（默认 `avsolatorio/GIST-small-Embedding-v0`）。
- `llm.model` / `llm.base_url` / `llm.api_key`：OpenAI 兼容模型与接口。
- `query.max_results` / `query.max_corpus`：推送数量与相似度计算的库上限。
- `query.include_abstract` / `query.translate_abstract`：卡片中是否附摘要及翻译。
- `query.include_tldr` / `query.tldr_language` / `query.tldr_max_words`：TLDR 开关、语言与长度。

## 本地运行与调试
- **本地运行**：直接执行 `python main.py`（读取配置并立即推送）。
  - 程序会自动检测配置的 Webhook（飞书或企业微信）并相应发送。
  - 如果同时配置了飞书和企业微信，程序会优先使用企业微信。
  - 对于企业微信，消息会自动按 1000 字符分割成多条消息，避免超过 4096 字符限制。
  - 这是推荐的本地运行和调试方式，可以快速验证配置和功能。
- **测试企业微信 Webhook**：使用 `python test_wechat.py <webhook_url>` 测试企业微信 Webhook 是否正常工作。
  - 测试脚本可以测试不同长度的消息，帮助诊断问题。
  - 也可以设置环境变量：`export WECHAT_WEBHOOK=<url> && python test_wechat.py`
- 如只想测试消息样式，可先设置 `FEISHU_TEST_WEBHOOK` 或 `WECHAT_TEST_WEBHOOK`；发送成功后再切换正式 Webhook。
- 调优建议：库很大时可调低 `query.max_corpus` 或 `zotero.max_items` 以加速。

## 提示
- LLM 调用使用 `response_format={"type": "json_object"}`，需确保模型支持 JSON 输出。
- 优先使用环境变量传密钥，便于 CI/容器。
- 如果使用自建/本地 LLM，设置好 `llm.base_url`、`llm.model` 与任意伪 API Key 即可。
- 企业微信单条消息限制为 4096 字符，程序会自动按 1000 字符分割成多条消息发送。