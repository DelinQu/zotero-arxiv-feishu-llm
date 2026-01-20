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


def _paper_md(idx: int, paper: Dict[str, str], max_abstract_length: int = 500) -> str:
    """将单篇论文转换为Markdown格式"""
    title = paper.get("title", "Untitled")
    # 限制标题长度，避免过长
    if len(title) > 200:
        title = title[:200] + "..."
    
    link = paper.get("link") or paper.get("url")
    score = paper.get("score")
    score_text = f"{score:.2f}" if isinstance(score, (int, float)) else "N/A"
    stars = _score_to_stars(score if isinstance(score, (int, float)) else None)
    abstract = paper.get("abstract") or ""
    abstract_zh = paper.get("abstract_zh") or ""
    tldr = paper.get("tldr") or ""
    authors = paper.get("authors") or []
    tags = paper.get("tags") or []
    
    # 限制关键词数量
    keywords = ", ".join(tags[:4])  # 减少到4个关键词
    if len(keywords) > 150:  # 限制关键词总长度
        keywords = keywords[:150] + "..."
    
    # 限制作者数量
    if authors:
        if len(authors) <= 3:
            author_line = ", ".join(authors)
        else:
            author_line = ", ".join(authors[:2] + ["...", authors[-1]])
        # 限制作者行长度
        if len(author_line) > 200:
            author_line = author_line[:200] + "..."
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
        # 限制链接文本长度
        if len(link_text) > 50:
            link_text = link_text[:50] + "..."
        score_line += f" | [{link_text}]({link})"
    lines.append(score_line)
    
    # 作者
    if author_line:
        lines.append(f"**作者:** {author_line}")
    
    # 关键词
    if keywords:
        lines.append(f"**关键词:** {keywords}")
    
    # TLDR或摘要（限制长度以避免单条消息过长）
    if tldr:
        tldr_text = tldr.replace('TLDR: ', '')
        if len(tldr_text) > max_abstract_length:
            tldr_text = tldr_text[:max_abstract_length] + "..."
        lines.append(f"**TLDR:** {tldr_text}")
    elif abstract_zh:
        if len(abstract_zh) > max_abstract_length:
            abstract_zh = abstract_zh[:max_abstract_length] + "..."
        lines.append(f"**摘要(中文):** {abstract_zh}")
    elif abstract:
        if len(abstract) > max_abstract_length:
            abstract = abstract[:max_abstract_length] + "..."
        lines.append(f"**摘要:** {abstract}")
    
    return "\n".join(lines)


def build_wechat_markdown(
    title: str,
    query: str,
    papers: List[Dict[str, str]],
) -> Dict:
    """构建企业微信Markdown格式的消息内容（已废弃，保留用于兼容）"""
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


def build_single_paper_message(
    idx: int,
    total: int,
    paper: Dict[str, str],
    title: str = "每日论文推送",
) -> Dict:
    """构建单篇论文的企业微信Markdown消息
    
    企业微信Markdown消息最大长度为4096字符，需要严格控制。
    """
    MAX_LENGTH = 4096
    date_str = datetime.now().strftime('%Y年%m月%d日')
    
    # 构建头部（预留一些空间）
    header = f"# {title}\n\n📚 **第 {idx}/{total} 篇** | {date_str}\n\n"
    header_length = len(header)
    
    # 计算可用空间（预留50字符作为安全边界）
    available_length = MAX_LENGTH - header_length - 50
    
    # 逐步尝试不同的摘要长度
    for max_abstract_len in [600, 400, 250, 150, 100]:
        paper_content = _paper_md(idx, paper, max_abstract_length=max_abstract_len)
        markdown_content = header + paper_content
        
        if len(markdown_content) <= MAX_LENGTH:
            break
    else:
        # 如果所有尝试都失败，强制截断
        paper_content = _paper_md(idx, paper, max_abstract_length=100)
        markdown_content = header + paper_content
        if len(markdown_content) > MAX_LENGTH:
            # 最后的安全措施：直接截断整个内容
            markdown_content = markdown_content[:MAX_LENGTH - 20] + "\n\n*（内容过长已截断）*"
    
    # 最终验证
    if len(markdown_content) > MAX_LENGTH:
        markdown_content = markdown_content[:MAX_LENGTH - 20] + "\n\n*（内容过长已截断）*"
    
    return {
        "msgtype": "markdown",
        "markdown": {
            "content": markdown_content
        }
    }


def build_summary_message(
    title: str,
    total: int,
) -> Dict:
    """构建摘要消息（第一条消息）"""
    date_str = datetime.now().strftime('%Y年%m月%d日')
    
    markdown_content = (
        f"# {title}\n\n"
        f"ฅʕ•̫͡•ʔฅ ◔.̮◔✧ (•̀ᴗ• ) ArXiv 小助手来啦！\n\n"
        f"📅 **日期:** {date_str}\n"
        f"📚 **找到论文:** {total} 篇\n\n"
        f"接下来将逐条推送每篇论文的详细信息..."
    )
    
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


def post_papers_separately(
    webhook_url: str,
    title: str,
    papers: List[Dict[str, str]],
    delay_seconds: float = 0.5,
) -> None:
    """将论文按4000字符长度分成多条消息推送
    
    Args:
        webhook_url: 企业微信Webhook URL
        title: 消息标题
        papers: 论文列表
        delay_seconds: 每条消息之间的延迟（秒），避免发送过快
    """
    import time
    
    MAX_MESSAGE_LENGTH = 1000  # 每条消息最大长度（留3096字符安全边界，确保不超过4096）
    total = len(papers)
    date_str = datetime.now().strftime('%Y年%m月%d日')
    
    if total == 0:
        # 如果没有论文，发送一条提示消息
        payload = build_summary_message(title, 0)
        post_to_wechat(webhook_url, payload)
        print("Sent summary message (no papers) to WeChat Work webhook.")
        return
    
    # 构建所有论文的内容
    paper_contents = []
    for idx, paper in enumerate(papers, 1):
        paper_md = _paper_md(idx, paper, max_abstract_length=400)  # 限制摘要长度
        paper_contents.append(paper_md)
    
    # 按长度分割消息
    messages = []
    current_message_parts = []
    current_length = 0
    
    # 第一条消息的头部
    header = f"# {title}\n\nฅʕ•̫͡•ʔฅ ◔.̮◔✧ (•̀ᴗ• ) ArXiv 小助手来啦！{date_str} 找到 **{total}** 📚 篇论文：\n\n---\n\n"
    header_length = len(header)
    current_length = header_length
    current_message_parts = [header]
    
    for idx, paper_content in enumerate(paper_contents, 1):
        separator = "\n\n---\n\n"
        paper_with_separator = paper_content + separator
        paper_length = len(paper_with_separator)
        
        # 检查添加这篇论文后是否会超过长度限制
        if current_length + paper_length > MAX_MESSAGE_LENGTH:
            # 如果当前消息已经有内容（除了header），先保存当前消息
            if len(current_message_parts) > 1:
                # 移除最后的分隔符
                last_part = current_message_parts[-1]
                if last_part.endswith(separator):
                    current_message_parts[-1] = last_part[:-len(separator)]
                final_message = "".join(current_message_parts)
                # 再次检查长度
                if len(final_message) > MAX_MESSAGE_LENGTH:
                    final_message = final_message[:MAX_MESSAGE_LENGTH - 20] + "\n\n*（内容过长已截断）*"
                messages.append(final_message)
            
            # 开始新消息（如果单篇论文就超过限制，需要截断）
            if paper_length > MAX_MESSAGE_LENGTH:
                # 单篇论文太长，需要截断
                truncated = paper_content[:MAX_MESSAGE_LENGTH - 50] + "\n\n*（内容过长已截断）*"
                current_message_parts = [truncated]
                current_length = len(truncated)
            else:
                # 开始新消息，添加简短的头部
                new_header = f"# {title} (续)\n\n"
                current_message_parts = [new_header, paper_with_separator]
                current_length = len(new_header) + paper_length
        else:
            # 可以添加到当前消息
            current_message_parts.append(paper_with_separator)
            current_length += paper_length
    
    # 添加最后一条消息
    if current_message_parts:
        # 移除最后的分隔符
        last_part = current_message_parts[-1]
        if last_part.endswith(separator):
            current_message_parts[-1] = last_part[:-len(separator)]
        final_message = "".join(current_message_parts)
        # 再次检查长度
        if len(final_message) > MAX_MESSAGE_LENGTH:
            final_message = final_message[:MAX_MESSAGE_LENGTH - 20] + "\n\n*（内容过长已截断）*"
        messages.append(final_message)
    
    # 发送所有消息
    total_messages = len(messages)
    for msg_idx, message_content in enumerate(messages, 1):
        try:
            # 最终严格长度检查（确保不超过4096）
            actual_length = len(message_content)
            if actual_length > 4096:
                print(f"警告: 消息 {msg_idx} 长度 {actual_length} 超过4096，正在截断...")
                message_content = message_content[:4050] + "\n\n*（内容过长已截断）*"
                actual_length = len(message_content)
            
            # 再次验证
            if actual_length > 4096:
                print(f"错误: 消息 {msg_idx} 截断后仍超过4096字符: {actual_length}")
                message_content = message_content[:4090] + "..."
            
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "content": message_content
                }
            }
            post_to_wechat(webhook_url, payload)
            print(f"✅ Sent message {msg_idx}/{total_messages} to WeChat Work webhook (length: {len(message_content)} chars)")
            
            # 在消息之间添加延迟，避免发送过快
            if msg_idx < total_messages and delay_seconds > 0:
                time.sleep(delay_seconds)
        except Exception as e:
            print(f"❌ Failed to send message {msg_idx}/{total_messages}: {e}")
            print(f"   消息长度: {len(message_content)} 字符")
            # 继续发送其他消息，不中断整个流程
            continue
    
    print(f"Finished sending all {total_messages} messages ({total} papers) to WeChat Work webhook.")
