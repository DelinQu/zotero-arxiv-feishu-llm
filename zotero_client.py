from typing import Any, Dict, List, Optional

from pyzotero import zotero


def _collection_names(client: zotero.Zotero) -> Dict[str, str]:
    collections = client.everything(client.collections())
    return {item["key"]: item["data"].get("name", "") for item in collections}


def _build_link(data: Dict[str, Any]) -> Optional[str]:
    if data.get("url"):
        return data["url"]
    if data.get("DOI"):
        return f"https://doi.org/{data['DOI']}"
    return None


def fetch_papers(
    library_id: str,
    api_key: str,
    library_type: str = "user",
    item_types: Optional[List[str]] = None,
    max_items: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch papers from Zotero and normalize the fields we need.
    """
    if item_types is None:
        item_types = ["conferencePaper", "journalArticle", "preprint"]

    client = zotero.Zotero(library_id, library_type, api_key)
    collection_map = _collection_names(client)
    type_filter = " || ".join(item_types)
    # Sort by latest added first so we match against newest Zotero entries.
    items_kwargs = dict(itemType=type_filter, sort="dateAdded", direction="desc")
    if max_items:
        raw_items = client.items(limit=max_items, **items_kwargs)
    else:
        raw_items = client.everything(client.items(**items_kwargs))
    papers: List[Dict[str, Any]] = []

    for entry in raw_items:
        data = entry.get("data", {})
        abstract = (data.get("abstractNote") or "").strip()
        title = (data.get("title") or "").strip()
        if not abstract or not title:
            continue

        collections = [collection_map.get(key, key) for key in data.get("collections", [])]
        tags = [t.get("tag") for t in data.get("tags", []) if t.get("tag")]
        authors = []
        for creator in data.get("creators", []):
            name = creator.get("name")
            if not name:
                first = creator.get("firstName") or ""
                last = creator.get("lastName") or ""
                name = f"{first} {last}".strip()
            if name:
                authors.append(name)

        paper = {
            "title": title,
            "abstract": abstract,
            "collections": collections,
            "tags": tags,
            "authors": authors,
            "link": _build_link(data),
        }
        papers.append(paper)
        if max_items and len(papers) >= max_items:
            break

    return papers
