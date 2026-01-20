# Zotero-Arxiv-Feishu-LLM
[中文说明](README.zh.md)

<p align="center">
  <img src="docs/teaser.png" width="80%">
</p>

Pull the latest arXiv papers, match them against your Zotero library via embeddings, optionally add TLDR/translation with an LLM, and send Feishu interactive cards or WeChat Work markdown messages. The pipeline stays minimal—no email or extra CI steps.

## What It Does
- Fetches new arXiv submissions for your chosen categories.
- Reads titles/abstracts/authors/tags from Zotero as your “interest profile.”
- Ranks arXiv papers by embedding similarity; keeps the most relevant ones.
- Optionally generates Chinese TLDRs and abstract translations; shows star ratings.
- Sends Feishu cards or WeChat Work markdown messages with titles, links, authors, tags, and previews.

## Flow
1) Read Zotero (skip entries without abstracts).  
2) Pull today’s arXiv papers (per `arxiv.query`).  
3) Compute Zotero ↔ arXiv similarity; keep top `query.max_results`.  
4) Optionally create TLDRs/translations and add relevance stars.  
5) Push Feishu cards or WeChat Work messages via Webhook.

## Requirements
- Python 3.10+.  
- Any OpenAI-compatible endpoint (official, Azure, or self-hosted).  
- Zotero Library ID + API Key, and a Feishu bot Webhook or WeChat Work bot Webhook.  
- CPU is enough; embedding/LLM calls go to remote APIs.

## Quick Start
1. Install deps: `pip install -r requirements.txt`
2. Copy config: `cp config.example.yaml config.yaml`
3. Fill `config.yaml` (or override secrets via env vars).  
4. Run: `python main.py` (fetches today’s arXiv and pushes to Webhook).  
5. For safe dry-runs, set `FEISHU_TEST_WEBHOOK`.

## Zotero Setup
- Create a Private Key in Zotero web: Settings → Feeds/API → check Library access; save the API Key.
- Find Library ID: personal libraries show UserID on Feeds/API; group libraries use the numeric ID in `https://www.zotero.org/groups/<group_id>`.
- Set `zotero.library_id`, `zotero.api_key`, `zotero.library_type` (`user` or `group`) in `config.yaml`; adjust `item_types` (e.g., add `book`, `thesis`) and `max_items` to speed up large libraries.
- Entries without abstracts are skipped; add abstracts in Zotero to improve matching quality.

## OpenAI-Style API
- Uses the chat/completions endpoint with `response_format={"type": "json_object"}` for structured output.
- Configure `llm.base_url`, `llm.model`, `llm.api_key` (or env `LLM_BASE_URL` / `LLM_MODEL` / `LLM_API_KEY`) for official OpenAI, Azure OpenAI, self-hosted gateways, or local services.
- Ensure the model supports JSON output; otherwise switch models or disable TLDR/translation.
- `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` are also supported and equivalent to `LLM_*`.

## Feishu Setup
- In your Feishu group, add a "Custom Bot" and copy the Webhook (see [official guide](https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot)).
- Cards are sent directly via Webhook; tweak `feishu.header_template` / `feishu.title` for styling.

## WeChat Work Setup
- In your WeChat Work group chat, add a "Custom Bot" (群机器人) and copy the Webhook URL (see [official guide](https://developer.work.weixin.qq.com/document/path/91770)).
- Messages are sent in Markdown format via Webhook; configure `wechat.webhook_url` / `wechat.title` in `config.yaml`.
- **Message Length**: Due to WeChat Work's 4096 character limit, messages are automatically split into multiple messages of up to 1000 characters each.
- **Priority**: If both Feishu and WeChat Work webhooks are configured, WeChat Work takes priority.

## Secrets & Env Vars
Priority: env vars > `config.yaml` > `config.example.yaml`.

| Name | Required | Source | Notes |
| --- | --- | --- | --- |
| `FEISHU_WEBHOOK` | No* | Secret / env | `LARK_WEBHOOK` also works; use `FEISHU_TEST_WEBHOOK` for dry-runs. *Required if WeChat Work not configured. |
| `WECHAT_WEBHOOK` | No* | Secret / env | `WECHAT_WORK_WEBHOOK` also works; use `WECHAT_TEST_WEBHOOK` for dry-runs. *Required if Feishu not configured. |
| `ZOTERO_ID` | Yes | Secret / env | Zotero library ID. |
| `ZOTERO_KEY` | Yes | Secret / env | Zotero API key. |
| `ZOTERO_LIBRARY_TYPE` | Yes | Secret / env | `user` or `group`. |
| `LLM_API_KEY` | Yes | Secret / env | OpenAI-compatible API key. |
| `LLM_MODEL` | Yes | Secret / env | Model name. |
| `LLM_BASE_URL` | Yes | Secret / env | Use default for official OpenAI. |
| `OPENAI_API_KEY` | No | Secret / env | Alias of `LLM_API_KEY`. |
| `OPENAI_MODEL` | No | Secret / env | Alias of `LLM_MODEL`. |
| `OPENAI_BASE_URL` | No | Secret / env | Alias of `LLM_BASE_URL`. |

## Config Highlights (`config.yaml`)
- `feishu.webhook_url`, `feishu.title`, `feishu.header_template` (blue/wathet/turquoise/green/yellow/orange/red/carmine; `#DAE3FA` maps to wathet).
- `wechat.webhook_url`, `wechat.title` for WeChat Work bot configuration.
- `arxiv.source` (`rss` or `api`), `arxiv.query`, `arxiv.max_results`, `arxiv.days_back` (supports fractional days for hours) for arXiv fetching/window.
- `arxiv.rss_wait_minutes` / `arxiv.rss_retry_minutes`: when using RSS, keep polling for new papers if the feed is still empty (e.g. before daily update).
- Scheduling: GitHub Actions `on.schedule` cron controls when the run is queued.
- `zotero.library_id`, `zotero.api_key`, `zotero.library_type`, `zotero.item_types`, `zotero.max_items` for access/filters.
- `embedding.model` (default `avsolatorio/GIST-small-Embedding-v0`).
- `llm.model`, `llm.base_url`, `llm.api_key` for OpenAI-compatible calls.
- `query.max_results`, `query.max_corpus` for push count and similarity corpus cap.
- `query.include_abstract`, `query.translate_abstract` to show abstracts and translations.
- `query.include_tldr`, `query.tldr_language`, `query.tldr_max_words` for TLDR control.

## Run & Debug
- **Local run**: `python main.py` (reads config and sends immediately).
  - The script will automatically detect which webhook is configured (Feishu or WeChat Work) and send accordingly.
  - If both are configured, WeChat Work takes priority.
  - For WeChat Work, messages are automatically split into chunks of 1000 characters to avoid the 4096 character limit.
- **Test WeChat Webhook**: Use `python test_wechat.py <webhook_url>` to test if your WeChat Work webhook is working correctly.
  - The test script can also test different message lengths and help diagnose issues.
- To test without affecting production, set `FEISHU_TEST_WEBHOOK` or `WECHAT_TEST_WEBHOOK`, then switch to the real Webhook.
- For large Zotero libraries, lower `query.max_corpus` or `zotero.max_items` to speed up.

## GitHub Actions
- Workflow `.github/workflows/run.yml`:  
  - `run` job: scheduled only (uses Feishu).
  - `test` job: manual only, uses `FEISHU_TEST_WEBHOOK` for safe drills.
- Workflow `.github/workflows/run_ep_wechat.yml`:
  - `run` job: scheduled only (uses WeChat Work).
  - `test` job: manual only, uses `WECHAT_TEST_WEBHOOK` for safe drills.
- In your repo (or fork) Settings → Secrets, add the env vars above; the workflow copies `config.example.yaml` to `config.yaml` and runs `python main.py`.
- Want zero local setup? Fork this repo → add Secrets in your fork → open Actions and manually trigger `run` or `test`. Tweak `config.example.yaml` / `arxiv.query` in your fork and rerun.

## Notes
- LLM calls expect JSON output; pick a model that supports it.
- Prefer env vars for secrets (CI/containers).
- For self-hosted/local LLMs, set `llm.base_url`, `llm.model`, and any placeholder API key.
- WeChat Work has a 4096 character limit per message; messages are automatically split into chunks of 1000 characters.