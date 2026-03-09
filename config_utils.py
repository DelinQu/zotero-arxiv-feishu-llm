import os
from typing import Dict

import yaml


PLACEHOLDER_STRINGS = {
    "",
    "cli_xxx",
    "xxx",
    "your-webhook",
    "your-key",
    "your-zotero-api-key",
    "sk-...",
}


def has_config_value(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return False
        lower_normalized = normalized.lower()
        if lower_normalized in PLACEHOLDER_STRINGS:
            return False
        if "your-webhook" in lower_normalized or "your-key" in lower_normalized:
            return False
        return True
    return bool(value)


def load_config(path: str = "config.yaml") -> Dict:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Config file {path} not found. Copy config.example.yaml and fill in your settings."
        )
    with open(path, "r", encoding="utf-8") as file:
        cfg = yaml.safe_load(file) or {}

    cfg.setdefault("zotero", {})
    cfg.setdefault("feishu", {})
    cfg.setdefault("wechat", {})
    cfg.setdefault("llm", {})
    cfg.setdefault("query", {})
    cfg.setdefault("arxiv", {})
    cfg.setdefault("embedding", {})
    cfg.setdefault("output", {})
    cfg.setdefault("wiki", {})
    legacy_wiki = cfg.get("wiki", {}) or {}

    env_overrides = {
        ("zotero", "library_id"): ["ZOTERO_ID"],
        ("zotero", "api_key"): ["ZOTERO_KEY"],
        ("zotero", "library_type"): ["ZOTERO_LIBRARY_TYPE"],
        ("feishu", "webhook_url"): ["FEISHU_WEBHOOK", "LARK_WEBHOOK"],
        ("feishu", "app_id"): ["FEISHU_APP_ID", "LARK_APP_ID"],
        ("feishu", "app_secret"): ["FEISHU_APP_SECRET", "LARK_APP_SECRET"],
        ("wechat", "webhook_url"): ["WECHAT_WEBHOOK", "WECHAT_WORK_WEBHOOK"],
        ("llm", "api_key"): ["LLM_API_KEY", "OPENAI_API_KEY"],
        ("llm", "model"): ["LLM_MODEL", "OPENAI_MODEL"],
        ("llm", "base_url"): ["LLM_BASE_URL", "OPENAI_BASE_URL"],
        ("feishu", "parent_url"): [
            "FEISHU_PARENT_URL",
            "LARK_PARENT_URL",
        ],
    }
    for (section, key), env_keys in env_overrides.items():
        for env_key in env_keys:
            if os.getenv(env_key):
                cfg[section][key] = os.getenv(env_key)
                break

    cfg["feishu"].setdefault("title", "Zotero LLM Picks")
    cfg["feishu"].setdefault("header_template", "turquoise")
    if not cfg["feishu"].get("parent_url") and legacy_wiki.get("parent_url"):
        cfg["feishu"]["parent_url"] = legacy_wiki["parent_url"]
    if "update_parent_doc" not in cfg["feishu"] and "update_parent_doc" in legacy_wiki:
        cfg["feishu"]["update_parent_doc"] = legacy_wiki["update_parent_doc"]
    cfg["feishu"].setdefault("parent_url", "")
    cfg["feishu"].setdefault("update_parent_doc", True)
    cfg["wechat"].setdefault("title", "每日论文推送")
    cfg["zotero"].setdefault("library_type", "user")
    cfg["zotero"].setdefault("item_types", ["conferencePaper", "journalArticle", "preprint"])
    cfg["query"].setdefault("max_results", 5)
    cfg["query"].setdefault("include_abstract", True)
    cfg["query"].setdefault("translate_abstract", True)
    cfg["query"].setdefault("include_tldr", True)
    cfg["query"].setdefault("tldr_language", "Chinese")
    cfg["query"].setdefault("tldr_max_words", 80)
    cfg["query"].setdefault("max_corpus", 400)
    cfg["arxiv"].setdefault("query", "cs.AI+cs.CL+cs.LG")
    cfg["arxiv"].setdefault("max_results", 30)
    cfg["arxiv"].setdefault("days_back", 1)
    cfg["arxiv"].setdefault("only_new", True)
    cfg["arxiv"].setdefault("source", "rss")
    cfg["embedding"].setdefault("model", "avsolatorio/GIST-small-Embedding-v0")
    cfg["llm"].setdefault("temperature", 0.0)
    cfg["llm"].setdefault("base_url", "https://api.openai.com/v1")
    cfg["output"].setdefault("root_dir", "output/digests")
    cfg["output"].setdefault("include_figures", True)
    cfg["output"].setdefault("figure_pages", 3)
    return cfg


def validate_main_config(cfg: Dict) -> None:
    has_feishu_webhook = has_config_value(cfg.get("feishu", {}).get("webhook_url"))
    has_feishu_docs = has_config_value(cfg.get("feishu", {}).get("app_id")) and has_config_value(
        cfg.get("feishu", {}).get("app_secret")
    )
    has_wiki_parent = has_config_value(cfg.get("feishu", {}).get("parent_url"))
    has_wechat = has_config_value(cfg.get("wechat", {}).get("webhook_url"))

    if not has_feishu_webhook and not has_feishu_docs and not has_wechat:
        raise ValueError(
            "至少需要配置 feishu.webhook_url、飞书文档应用（feishu.app_id + feishu.app_secret）或 wechat.webhook_url 之一"
        )
    if has_feishu_docs and not has_wiki_parent:
        raise ValueError("启用飞书文档发布时，必须配置 feishu.parent_url")

    required = [
        ("zotero", "library_id"),
        ("zotero", "api_key"),
        ("llm", "api_key"),
        ("llm", "model"),
        ("arxiv", "query"),
    ]
    missing = [
        (section, key)
        for (section, key) in required
        if not has_config_value(cfg.get(section, {}).get(key))
    ]
    if missing:
        missing_str = ", ".join([f"{section}.{key}" for section, key in missing])
        raise ValueError(f"Missing required config values: {missing_str}")


def validate_wiki_config(cfg: Dict) -> None:
    has_feishu_docs = has_config_value(cfg.get("feishu", {}).get("app_id")) and has_config_value(
        cfg.get("feishu", {}).get("app_secret")
    )
    has_wiki_parent = has_config_value(cfg.get("feishu", {}).get("parent_url"))
    if not has_feishu_docs:
        raise ValueError("测试 Wiki 发布时，必须配置 feishu.app_id 和 feishu.app_secret")
    if not has_wiki_parent:
        raise ValueError("测试 Wiki 发布时，必须配置 feishu.parent_url")
