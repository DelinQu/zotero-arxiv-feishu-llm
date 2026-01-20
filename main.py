import os
from typing import Dict, List

import yaml

from arxiv_fetcher import fetch_daily_arxiv
from feishu import build_post_content, post_to_feishu
from wechat import post_papers_separately
from llm_utils import LLMScorer
from similarity import rerank_by_embedding
from zotero_client import fetch_papers


def load_config(path: str = "config.yaml") -> Dict:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Config file {path} not found. Copy config.example.yaml and fill in your settings."
        )
    with open(path, "r", encoding="utf-8") as file:
        cfg = yaml.safe_load(file) or {}

    # Environment variable overrides for secrets
    cfg.setdefault("zotero", {})
    cfg.setdefault("feishu", {})
    cfg.setdefault("wechat", {})
    cfg.setdefault("llm", {})
    cfg.setdefault("query", {})
    cfg.setdefault("arxiv", {})
    cfg.setdefault("embedding", {})

    env_overrides = {
        ("zotero", "library_id"): ["ZOTERO_ID"],
        ("zotero", "api_key"): ["ZOTERO_KEY"],
        ("zotero", "library_type"): ["ZOTERO_LIBRARY_TYPE"],
        ("feishu", "webhook_url"): ["FEISHU_WEBHOOK", "LARK_WEBHOOK"],
        ("wechat", "webhook_url"): ["WECHAT_WEBHOOK", "WECHAT_WORK_WEBHOOK"],
        ("llm", "api_key"): ["LLM_API_KEY", "OPENAI_API_KEY"],
        ("llm", "model"): ["LLM_MODEL", "OPENAI_MODEL"],
        ("llm", "base_url"): ["LLM_BASE_URL", "OPENAI_BASE_URL"],
    }
    for (section, key), env_keys in env_overrides.items():
        for env_key in env_keys:
            if os.getenv(env_key):
                cfg[section][key] = os.getenv(env_key)
                break

    # Defaults
    cfg["feishu"].setdefault("title", "Zotero LLM Picks")
    cfg["feishu"].setdefault("header_template", "turquoise")
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
    cfg["arxiv"].setdefault("source", "rss")  # "rss" (default) or "api"
    cfg["embedding"].setdefault("model", "avsolatorio/GIST-small-Embedding-v0")
    cfg["llm"].setdefault("temperature", 0.0)
    cfg["llm"].setdefault("base_url", "https://api.openai.com/v1")

    # 检查通知方式：至少需要配置飞书或企业微信之一
    has_feishu = bool(cfg.get("feishu", {}).get("webhook_url"))
    has_wechat = bool(cfg.get("wechat", {}).get("webhook_url"))
    
    if not has_feishu and not has_wechat:
        raise ValueError("至少需要配置 feishu.webhook_url 或 wechat.webhook_url 之一")
    
    required = [
        ("zotero", "library_id"),
        ("zotero", "api_key"),
        ("llm", "api_key"),
        ("llm", "model"),
        ("arxiv", "query"),
    ]
    missing = [(s, k) for (s, k) in required if not cfg.get(s, {}).get(k)]
    if missing:
        missing_str = ", ".join([f"{s}.{k}" for s, k in missing])
        raise ValueError(f"Missing required config values: {missing_str}")
    return cfg


def enrich_with_llm(papers: List[Dict], scorer: LLMScorer, query: Dict[str, str]) -> List[Dict]:
    translate_abstract = bool(query.get("translate_abstract", True))
    include_abstract = bool(query.get("include_abstract", True))
    include_tldr = bool(query.get("include_tldr", True))
    tldr_lang = query.get("tldr_language", "Chinese")
    tldr_max_words = int(query.get("tldr_max_words", 80))
    results: List[Dict] = []
    for paper in papers:
        enriched = {**paper}
        if include_abstract and translate_abstract and paper.get("abstract"):
            enriched["abstract_zh"] = scorer.translate(paper["abstract"], target_lang="Chinese")
        if include_tldr:
            enriched["tldr"] = scorer.summarize(
                title=paper.get("title", ""),
                abstract=paper.get("abstract", ""),
                target_lang=tldr_lang,
                max_words=tldr_max_words,
            )
        results.append(enriched)
    return results


def main():
    config = load_config()

    print("Loading Zotero papers...")
    max_items = config["zotero"].get("max_items")
    if max_items is not None:
        max_items = int(max_items)
    zotero_papers = fetch_papers(
        library_id=config["zotero"]["library_id"],
        api_key=config["zotero"]["api_key"],
        library_type=config["zotero"]["library_type"],
        item_types=config["zotero"]["item_types"],
        max_items=max_items,
    )
    print(f"Fetched {len(zotero_papers)} papers with abstracts from Zotero.")

    print("Fetching arXiv daily papers...")
    arxiv_papers = fetch_daily_arxiv(
        arxiv_query=config["arxiv"]["query"],
        max_results=int(config["arxiv"].get("max_results", 30)),
        only_new=bool(config["arxiv"].get("only_new", True)),
        days_back=float(config["arxiv"].get("days_back", 1)),
        source=str(config["arxiv"].get("source", "rss")).lower(),
        rss_wait_minutes=int(config["arxiv"].get("rss_wait_minutes", 30))
        if config["arxiv"].get("rss_wait_minutes") is not None
        else None,
        rss_retry_minutes=int(config["arxiv"].get("rss_retry_minutes", 15)),
    )
    print(f"Fetched {len(arxiv_papers)} arXiv candidates.")
    if not arxiv_papers:
        print("No new arXiv papers. Exit.")
        return

    print("Reranking by Zotero similarity...")
    ranked = rerank_by_embedding(
        candidates=arxiv_papers,
        corpus=zotero_papers,
        model_name=config["embedding"]["model"],
        top_k=int(config["query"].get("max_results", 5)),
        max_corpus=int(config["query"].get("max_corpus", 400)) if config["query"].get("max_corpus") else None,
    )
    print(f"Top {len(ranked)} matched papers after rerank.")
    if not ranked:
        print("No matching papers after rerank.")
        return

    scorer = LLMScorer(
        api_key=config["llm"]["api_key"],
        base_url=config["llm"]["base_url"],
        model=config["llm"]["model"],
        temperature=float(config["llm"].get("temperature", 0.0)),
    )

    matches = enrich_with_llm(ranked, scorer, config["query"])
    print(f"Enriched {len(matches)} matched papers.")

    # 根据配置选择发送到飞书或企业微信
    if config.get("wechat", {}).get("webhook_url"):
        # 发送到企业微信（每条论文一条消息）
        post_papers_separately(
            webhook_url=config["wechat"]["webhook_url"],
            title=config["wechat"].get("title", "每日论文推送"),
            papers=matches,
            delay_seconds=0.5,  # 每条消息间隔0.5秒，避免发送过快
        )
    elif config.get("feishu", {}).get("webhook_url"):
        # 发送到飞书
        payload = build_post_content(
            title=config["feishu"]["title"],
            query=config["arxiv"]["query"],
            papers=matches,
            header_template=config["feishu"].get("header_template", "turquoise"),
        )
        post_to_feishu(config["feishu"]["webhook_url"], payload)
        print("Sent to Feishu webhook.")
    else:
        raise ValueError("未配置任何通知方式（飞书或企业微信）")


if __name__ == "__main__":
    main()
