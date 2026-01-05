"""
Simple dry-run script to verify: arXiv daily fetch → Zotero similarity rerank → LLM enrich → Feishu payload.

Usage:
  python test_run.py               # only print matches and payload
  python test_run.py --send        # actually send to Feishu webhook
  python test_run.py --limit 200   # limit Zotero items for faster embedding
"""

import argparse
from pprint import pprint

from arxiv_fetcher import fetch_daily_arxiv
from feishu import build_post_content, post_to_feishu
from llm_utils import LLMScorer
from main import enrich_with_llm, load_config
from similarity import rerank_by_embedding
from zotero_client import fetch_papers


def run(send: bool, limit: int = None):
    cfg = load_config()
    arxiv_papers = fetch_daily_arxiv(
        arxiv_query=cfg["arxiv"]["query"],
        max_results=int(cfg["arxiv"].get("max_results", 30)),
        only_new=bool(cfg["arxiv"].get("only_new", True)),
        days_back=int(cfg["arxiv"].get("days_back", 1)),
    )

    print("Loading Zotero papers...")
    zotero_papers = fetch_papers(
        library_id=cfg["zotero"]["library_id"],
        api_key=cfg["zotero"]["api_key"],
        library_type=cfg["zotero"]["library_type"],
        item_types=cfg["zotero"]["item_types"],
        max_items=cfg["zotero"].get("max_items"),
    )
    print(f"Fetched {len(zotero_papers)} papers (with abstract).")
    print("Fetching arXiv daily papers...")
    print(f"Fetched {len(arxiv_papers)} arXiv candidates.")
    
    # print the fetched arxiv paper title
    for i, paper in enumerate(arxiv_papers):
        print(i, paper["title"])

    query_max_results = limit or cfg["query"].get("max_results", 5)

    ranked = rerank_by_embedding(
        candidates=arxiv_papers,
        corpus=zotero_papers,
        model_name=cfg["embedding"]["model"],
        top_k=int(query_max_results),
        max_corpus=int(cfg["query"].get("max_corpus", 400)) if cfg["query"].get("max_corpus") else None,
    )

    scorer = LLMScorer(
        api_key=cfg["llm"]["api_key"],
        base_url=cfg["llm"]["base_url"],
        model=cfg["llm"]["model"],
        temperature=float(cfg["llm"].get("temperature", 0.0)),
    )
    matches = enrich_with_llm(ranked, scorer, cfg["query"])

    print("\nTop matches:")
    for idx, p in enumerate(matches, 1):
        print(f"{idx}. {p.get('title')} — score={p.get('score'):.3f}")

    payload = build_post_content(
        title=cfg["feishu"]["title"],
        query=cfg["arxiv"]["query"],
        papers=matches,
        header_template=cfg["feishu"].get("header_template", "turquoise"),
    )
    print("\nFeishu payload preview:")
    pprint(payload)

    if send:
        post_to_feishu(cfg["feishu"]["webhook_url"], payload)
        print("\nSent to Feishu.")
    else:
        print("\nSend skipped (use --send to push to Feishu).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dry-run Feishu push with arXiv+Zotero rerank.")
    parser.add_argument("--send", action="store_true", help="Actually send to Feishu (default: preview only).")
    parser.add_argument("--limit", type=int, help="Limit number of Zotero items to fetch for faster tests.")
    args = parser.parse_args()
    run(send=args.send, limit=args.limit)
