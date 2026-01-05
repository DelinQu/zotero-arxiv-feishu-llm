from typing import Dict, List
from datetime import datetime
import requests


def _header_template(value: str) -> str:
    """
    Feishu supports limited templates. If a custom color (e.g., #DAE3FA) is given,
    map to the closest built-in light blue (wathet).
    """
    if value and value.startswith("#"):
        return "wathet"
    return value or "wathet"


def _score_to_stars(score: float) -> str:
    if score is None:
        return "N/A"
    level = max(1, min(5, int(round(score * 5))))
    return "⭐" * level


def _short_link(url: str) -> str:
    if not url:
        return ""
    link = url.replace("https://", "").replace("http://", "")
    return link.rstrip("/")


def _paper_md(idx: int, paper: Dict[str, str]) -> str:
    title = paper.get("title", "Untitled")
    link = paper.get("link") or paper.get("url")
    score = paper.get("score")
    score_text = f"{score:.2f}" if isinstance(score, (int, float)) else "N/A"
    stars = _score_to_stars(score if isinstance(score, (int, float)) else None)
    abstract = paper.get("abstract") or ""
    abstract_zh = paper.get("abstract_zh") or ""
    tldr = paper.get("tldr") or ""
    authors = paper.get("authors") or []
    tags = paper.get("tags") or []
    keywords = ", ".join(tags[:6])
    if authors:
        if len(authors) <= 5:
            author_line = ", ".join(authors)
        else:
            author_line = ", ".join(authors[:4] + ["...", authors[-1]])
    else:
        author_line = ""
    link_text = _short_link(link)

    if link:
        title_line = f"**{idx}. [{title}]({link})**"
    else:
        title_line = f"**{idx}. {title}**"

    lines = [
        title_line,
        f"{stars}  相关度: {score_text}" + (f" | [{link_text[:-2]}]({link})" if link_text else ""),
    ]
    if author_line:
        lines.append(f"作者: {author_line}")
    if keywords:
        lines.append(f"关键词: {keywords}")
    if tldr:
        lines.append("TLDR: " + tldr.replace("TLDR: ", ""))
    elif abstract_zh:
        lines.append(f"摘要(中文): {abstract_zh}")
    elif abstract:
        lines.append(f"摘要: {abstract}")
    return "\n".join(lines)


def _render_list_md(papers: List[Dict[str, str]]) -> str:
    parts = []
    for idx, paper in enumerate(papers, 1):
        parts.append(_paper_md(idx, paper))
    return "\n\n".join(parts)


def build_post_content(
    title: str,
    query: str,
    papers: List[Dict[str, str]],
    header_template: str = "turquoise",
) -> Dict:
    
    total = len(papers)
    elements: List[Dict] = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"ฅʕ•̫͡•ʔฅ ◔.̮◔✧ (•̀ᴗ• ) ArXiv 小助手来啦！{datetime.now().strftime('%Y年%m月%d日')} 找到 {total} 📚 篇论文：",
            },
        }
    ]

    if total == 0:
        elements.append(
            {"tag": "div", "text": {"tag": "lark_md", "content": "未找到匹配的论文。"}}
        )
    else:
        remainder_md = _render_list_md(papers)
        elements.append({"tag": "hr"})
        # 使用常规 div 以保持正常字号和颜色
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": remainder_md}})

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": _header_template(header_template),
            },
            "elements": elements,
        },
    }


def post_to_feishu(webhook_url: str, payload: Dict) -> None:
    headers = {"Content-Type": "application/json"}
    response = requests.post(webhook_url, json=payload, headers=headers, timeout=10)
    if response.status_code != 200:
        raise RuntimeError(
            f"Feishu webhook failed: {response.status_code} {response.text}"
        )
