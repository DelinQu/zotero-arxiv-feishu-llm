from typing import Dict, List
from datetime import datetime
import requests


def _score_to_stars(score: float) -> str:
    """将相似度分数转换为星级显示"""
    if score is None:
        return "N/A"
    level = max(1, min(5, int(round(score * 5))))
    return "⭐" * level


def _short_link(url: str) -> str:
    """简化链接显示"""
    if not url:
        return ""
    link = url.replace("https://", "").replace("http://", "")
    return link.rstrip("/")


def _paper_md(idx: int, paper: Dict[str, str]) -> str:
    """将单篇论文转换为Markdown格式"""
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

    lines = []
    # 标题
    if link:
        lines.append(f"**{idx}. [{title}]({link})**")
    else:
        lines.append(f"**{idx}. {title}**")
    
    # 评分和链接
    score_line = f"{stars} 相关度: {score_text}"
    if link_text:
        score_line += f" | [{link_text}]({link})"
    lines.append(score_line)
    
    # 作者
    if author_line:
        lines.append(f"**作者:** {author_line}")
    
    # 关键词
    if keywords:
        lines.append(f"**关键词:** {keywords}")
    
    # TLDR或摘要
    if tldr:
        lines.append(f"**TLDR:** {tldr.replace('TLDR: ', '')}")
    elif abstract_zh:
        lines.append(f"**摘要(中文):** {abstract_zh}")
    elif abstract:
        # 企业微信Markdown对长文本支持有限，截断过长的摘要
        if len(abstract) > 300:
            abstract = abstract[:300] + "..."
        lines.append(f"**摘要:** {abstract}")
    
    return "\n".join(lines)


def build_wechat_markdown(
    title: str,
    query: str,
    papers: List[Dict[str, str]],
) -> Dict:
    """构建企业微信Markdown格式的消息内容"""
    total = len(papers)
    date_str = datetime.now().strftime('%Y年%m月%d日')
    
    # 构建Markdown内容
    content_parts = [
        f"# {title}",
        "",
        f"ฅʕ•̫͡•ʔฅ ◔.̮◔✧ (•̀ᴗ• ) ArXiv 小助手来啦！{date_str} 找到 **{total}** 📚 篇论文：",
        "",
    ]
    
    if total == 0:
        content_parts.append("未找到匹配的论文。")
    else:
        content_parts.append("---")
        content_parts.append("")
        for idx, paper in enumerate(papers, 1):
            content_parts.append(_paper_md(idx, paper))
            if idx < total:
                content_parts.append("")
                content_parts.append("---")
                content_parts.append("")
    
    markdown_content = "\n".join(content_parts)
    
    return {
        "msgtype": "markdown",
        "markdown": {
            "content": markdown_content
        }
    }


def post_to_wechat(webhook_url: str, payload: Dict) -> None:
    """发送消息到企业微信Webhook"""
    headers = {"Content-Type": "application/json"}
    response = requests.post(webhook_url, json=payload, headers=headers, timeout=10)
    
    if response.status_code != 200:
        raise RuntimeError(
            f"企业微信Webhook请求失败: HTTP {response.status_code} {response.text}"
        )
    
    # 企业微信返回格式: {"errcode": 0, "errmsg": "ok"}
    try:
        result = response.json()
        if result.get("errcode") != 0:
            raise RuntimeError(
                f"企业微信Webhook返回错误: errcode={result.get('errcode')}, errmsg={result.get('errmsg')}"
            )
    except ValueError:
        # 如果响应不是JSON，使用原始文本
        raise RuntimeError(
            f"企业微信Webhook返回非JSON格式: {response.text}"
        )
