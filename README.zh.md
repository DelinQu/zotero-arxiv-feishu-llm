# Zotero-Arxiv-Feishu-LLM

<p align="center">
  <img src="docs/teaser.png" width="80%">
</p>

从 arXiv 获取当天的新论文，基于嵌入相似度匹配你的 Zotero 库（作为兴趣集），用 LLM 生成 TLDR/翻译，并通过飞书卡片推送。默认只有最小链路，去掉了邮件、复杂 CI 等附加流程。

## 功能概览
- 拉取当天 arXiv 新稿，按指定学科/关键词过滤。
- 从 Zotero 库读取标题/摘要/作者/标签等，作为兴趣参考。
- 使用句向量模型计算相似度，截取最相关的论文。
- 可选生成中文 TLDR、摘要翻译；评分星级一并展示。
- 通过飞书自定义机器人推送卡片，预览前 N 篇，便于快速浏览。

## 工作流程
1) 读取 Zotero 库（忽略没有摘要的条目），保留元信息。  
2) 拉取当天 arXiv 新稿（按 `arxiv.query`）。  
3) 计算 arXiv ↔ Zotero 摘要的相似度，按分数排序并截取 `query.max_results`。  
4) 可选生成 TLDR、摘要翻译；添加相关度星级。  
5) 通过飞书 Webhook 发送互动卡片，含标题/链接、作者、关键词、TLDR/摘要预览。

## 环境要求
- Python 3.10+。
- 可访问任意 OpenAI 兼容接口（官方或自建均可）。
- 准备好 Zotero 的 Library ID 与 API Key，以及飞书机器人的 Webhook。
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

## 密钥与环境变量
敏感字段可通过环境变量注入（CI/容器推荐），优先级：环境变量 > `config.yaml` > `config.example.yaml`。

必填环境变量（Secrets）：
- `FEISHU_WEBHOOK`（或 `LARK_WEBHOOK`；测试可用 `FEISHU_TEST_WEBHOOK`）
- `ZOTERO_ID`
- `ZOTERO_KEY`
- `LLM_API_KEY`
- `LLM_MODEL`
- `LLM_BASE_URL`（使用官方 OpenAI 可填默认）

可选：`OPENAI_API_KEY` / `OPENAI_MODEL` / `OPENAI_BASE_URL`（等价于 LLM_*）。

## GitHub Actions
工作流 `.github/workflows/run.yml`：
- `run` Job：每天 10:00 CST 定时运行，可在 Actions 页面手动触发。
- `test` Job：仅手动触发时运行，使用 `FEISHU_TEST_WEBHOOK`，便于演练不打扰正式群。

- 在仓库 Settings → Secrets 添加上述环境变量后，即可点击 “Run workflow” 触发；工作流会自动复制 `config.example.yaml` 为 `config.yaml` 并执行 `python main.py`。
- 想无本地部署、直接在 GitHub 上用：Fork 仓库 → 在自己 Fork 的 Settings → Secrets 配好变量（同上）→ 打开 Actions 选项卡，手动触发 `run` 或 `test` 工作流即可，无需本地 clone；后续可在 Fork 里改 `config.example.yaml` / `arxiv.query` 等参数，再次运行。

## 配置项速览（`config.yaml`）
- `feishu.webhook_url`：飞书机器人 Webhook。
- `feishu.title` / `feishu.header_template`：卡片标题与头部色（blue / wathet / turquoise / green / yellow / orange / red / carmine；填 `#DAE3FA` 会自动映射为 wathet）。
- `arxiv.query` / `arxiv.max_results` / `arxiv.days_back`：arXiv RSS 查询与时间窗口。
- `zotero.library_id` / `zotero.api_key` / `zotero.library_type` / `zotero.item_types` / `zotero.max_items`：Zotero 访问与过滤。
- `embedding.model`：相似度嵌入模型（默认 `avsolatorio/GIST-small-Embedding-v0`）。
- `llm.model` / `llm.base_url` / `llm.api_key`：OpenAI 兼容模型与接口。
- `query.max_results` / `query.max_corpus`：推送数量与相似度计算的库上限。
- `query.include_abstract` / `query.translate_abstract`：卡片中是否附摘要及翻译。
- `query.include_tldr` / `query.tldr_language` / `query.tldr_max_words`：TLDR 开关、语言与长度。

## 本地运行与调试
- 直接运行：`python main.py`（读取配置并立即推送）。
- 如只想测试卡片样式，可先设置 `FEISHU_TEST_WEBHOOK`；发送成功后再切换正式 Webhook。
- 调优建议：库很大时可调低 `query.max_corpus` 或 `zotero.max_items` 以加速。

## 提示
- LLM 调用使用 `response_format={"type": "json_object"}`，需确保模型支持 JSON 输出。
- 优先使用环境变量传密钥，便于 CI/容器。
- 如果使用自建/本地 LLM，设置好 `llm.base_url`、`llm.model` 与任意伪 API Key 即可。
