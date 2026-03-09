from datetime import datetime
from typing import Dict, List

from arxiv_fetcher import fetch_daily_arxiv
from config_utils import has_config_value, load_config, validate_main_config
from daily_digest import generate_daily_digest
from feishu import build_post_content, post_to_feishu
from feishu_docs import FeishuDocsClient
from wechat import post_papers_separately
from llm_utils import LLMScorer
from naming import build_daily_doc_title
from similarity import rerank_by_embedding
from zotero_client import fetch_papers


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
    validate_main_config(config)
    generated_at = datetime.now()
    daily_title = build_daily_doc_title(
        config["feishu"].get("title") or config["wechat"].get("title", "每日论文推送"),
        generated_at=generated_at,
    )

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

    digest = generate_daily_digest(
        title=daily_title,
        query=config["arxiv"]["query"],
        papers=matches,
        output_root=config["output"].get("root_dir", "output/digests"),
        include_figures=bool(config["output"].get("include_figures", True)),
        figure_pages=int(config["output"].get("figure_pages", 3)),
        generated_at=generated_at,
    )
    print(f"Markdown digest written to {digest.markdown_path}")

    doc_url = ""
    doc_publish_error = ""
    if has_config_value(config.get("feishu", {}).get("app_id")) and has_config_value(
        config.get("feishu", {}).get("app_secret")
    ):
        try:
            print("Publishing digest to Feishu Docs...")
            doc_client = FeishuDocsClient(
                app_id=config["feishu"]["app_id"],
                app_secret=config["feishu"]["app_secret"],
                wiki_parent_url=config["feishu"].get("parent_url", ""),
                update_parent_doc=bool(config["feishu"].get("update_parent_doc", True)),
            )
            document = doc_client.publish_digest(
                title=daily_title,
                query=config["arxiv"]["query"],
                papers=digest.papers,
                generated_at=generated_at,
            )
            doc_url = document.document_url
            print(f"Feishu doc created: {doc_url}")
        except Exception as exc:
            doc_publish_error = str(exc)
            print(f"Feishu doc publish failed; continuing without doc link. Error: {doc_publish_error}")

    # 根据配置选择发送到飞书或企业微信
    if has_config_value(config.get("wechat", {}).get("webhook_url")):
        # 发送到企业微信（每条论文一条消息）
        post_papers_separately(
            webhook_url=config["wechat"]["webhook_url"],
            title=config["wechat"].get("title", "每日论文推送"),
            papers=digest.papers,
            delay_seconds=0.5,  # 每条消息间隔0.5秒，避免发送过快
        )
    elif has_config_value(config.get("feishu", {}).get("webhook_url")):
        # 发送到飞书
        payload = build_post_content(
            title=daily_title,
            query=config["arxiv"]["query"],
            papers=digest.papers,
            header_template=config["feishu"].get("header_template", "turquoise"),
            doc_url=doc_url,
        )
        post_to_feishu(config["feishu"]["webhook_url"], payload)
        print("Sent to Feishu webhook.")
        if doc_publish_error and not doc_url:
            print("Skipped Feishu doc link message because doc publish failed.")
    elif doc_url:
        print("Skipped chat notification; Feishu doc has been created.")
    else:
        print("Skipped chat notification; markdown digest generated locally only.")


if __name__ == "__main__":
    main()
