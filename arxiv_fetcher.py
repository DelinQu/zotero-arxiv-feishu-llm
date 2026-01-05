from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import arxiv
import feedparser


def _extract_new_ids(arxiv_query: str, only_new: bool = True, days_back: Optional[int] = 1) -> List[str]:
    feed = feedparser.parse(f"https://rss.arxiv.org/atom/{arxiv_query}")
    if "Feed error for query" in feed.feed.get("title", ""):
        raise ValueError(f"Invalid arXiv query: {arxiv_query}")

    cutoff = None
    if days_back is not None and days_back >= 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

    ids: List[str] = []
    for entry in feed.entries:
        announce_type = entry.get("arxiv_announce_type")
        if only_new and announce_type not in ("new", None):
            continue  # if field missing, treat as new; else require "new"
        if cutoff:
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            if published:
                published_dt = datetime(*published[:6], tzinfo=timezone.utc)
                if published_dt < cutoff:
                    continue
        ids.append(entry.id.removeprefix("oai:arXiv.org:"))
    return ids


def fetch_daily_arxiv(
    arxiv_query: str,
    max_results: int = 50,
    client: Optional[arxiv.Client] = None,
    only_new: bool = True,
    days_back: Optional[int] = 1,
) -> List[Dict]:
    """
    Fetch new arXiv papers (announced within `days_back`) for a given query string.
    Returns a list of dicts with title, abstract, authors, url, published.
    """
    ids = _extract_new_ids(arxiv_query, only_new=only_new, days_back=days_back)
    if not ids:
        return []
    if max_results > 0:
        ids = ids[:max_results]

    client = client or arxiv.Client(num_retries=3, delay_seconds=3)
    results: List[Dict] = []
    for i in range(0, len(ids), 20):
        search = arxiv.Search(id_list=ids[i : i + 20])
        for res in client.results(search):
            results.append(
                {
                    "title": res.title,
                    "abstract": res.summary,
                    "authors": [a.name for a in res.authors],
                    "url": res.entry_id.replace("http://", "https://"),
                    "link": res.entry_id.replace("http://", "https://"),
                    "published": res.published.date().isoformat() if res.published else "",
                }
            )
    return results
