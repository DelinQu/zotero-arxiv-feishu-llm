# Zotero-Arxiv-Feishu-LLM
[中文说明](README.zh.md)

<p align="center">
  <img src="docs/teaser.png" width="80%">
</p>

Pull the latest arXiv papers, match them against your Zotero library via embeddings, optionally add TLDR/translation with an LLM, and send Feishu interactive cards. The pipeline stays minimal—no email or extra CI steps.

## What It Does
- Fetches new arXiv submissions for your chosen categories.
- Reads titles/abstracts/authors/tags from Zotero as your “interest profile.”
- Ranks arXiv papers by embedding similarity; keeps the most relevant ones.
- Optionally generates Chinese TLDRs and abstract translations; shows star ratings.
- Sends Feishu cards with titles, links, authors, tags, and previews.

## Flow
1) Read Zotero (skip entries without abstracts).  
2) Pull today’s arXiv papers (per `arxiv.query`).  
3) Compute Zotero ↔ arXiv similarity; keep top `query.max_results`.  
4) Optionally create TLDRs/translations and add relevance stars.  
5) Push Feishu cards via Webhook.

## Requirements
- Python 3.10+.  
- Any OpenAI-compatible endpoint (official, Azure, or self-hosted).  
- Zotero Library ID + API Key, and a Feishu bot Webhook.  
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
- In your Feishu group, add a “Custom Bot” and copy the Webhook (see [official guide](https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot)).
- Cards are sent directly via Webhook; tweak `feishu.header_template` / `feishu.title` for styling.

## Secrets & Env Vars
Priority: env vars > `config.yaml` > `config.example.yaml`.

Required:
- `FEISHU_WEBHOOK` (or `LARK_WEBHOOK`; use `FEISHU_TEST_WEBHOOK` for dry-runs)
- `ZOTERO_ID`
- `ZOTERO_KEY`
- `LLM_API_KEY`
- `LLM_MODEL`
- `LLM_BASE_URL` (use default for official OpenAI)

Optional: `OPENAI_API_KEY` / `OPENAI_MODEL` / `OPENAI_BASE_URL` (aliases of `LLM_*`).

## Config Highlights (`config.yaml`)
- `feishu.webhook_url`, `feishu.title`, `feishu.header_template` (blue/wathet/turquoise/green/yellow/orange/red/carmine; `#DAE3FA` maps to wathet).
- `arxiv.query`, `arxiv.max_results`, `arxiv.days_back` for RSS filtering/window.
- `zotero.library_id`, `zotero.api_key`, `zotero.library_type`, `zotero.item_types`, `zotero.max_items` for access/filters.
- `embedding.model` (default `avsolatorio/GIST-small-Embedding-v0`).
- `llm.model`, `llm.base_url`, `llm.api_key` for OpenAI-compatible calls.
- `query.max_results`, `query.max_corpus` for push count and similarity corpus cap.
- `query.include_abstract`, `query.translate_abstract` to show abstracts and translations.
- `query.include_tldr`, `query.tldr_language`, `query.tldr_max_words` for TLDR control.

## Run & Debug
- Run: `python main.py` (reads config and sends immediately).
- To test card layout, set `FEISHU_TEST_WEBHOOK`, then switch to the real Webhook.
- For large Zotero libraries, lower `query.max_corpus` or `zotero.max_items` to speed up.

## GitHub Actions
- Workflow `.github/workflows/run.yml`:  
  - `run` job: daily at 10:00 CST, also manual.  
  - `test` job: manual only, uses `FEISHU_TEST_WEBHOOK` for safe drills.
- In your repo (or fork) Settings → Secrets, add the env vars above; the workflow copies `config.example.yaml` to `config.yaml` and runs `python main.py`.
- Want zero local setup? Fork this repo → add Secrets in your fork → open Actions and manually trigger `run` or `test`. Tweak `config.example.yaml` / `arxiv.query` in your fork and rerun.

## Notes
- LLM calls expect JSON output; pick a model that supports it.
- Prefer env vars for secrets (CI/containers).
- For self-hosted/local LLMs, set `llm.base_url`, `llm.model`, and any placeholder API key.
