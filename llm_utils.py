import json
from typing import Any, Dict

from openai import OpenAI


class LLMScorer:
    """
    Small helper that scores Zotero papers against a free-form query using an OpenAI-compatible API.
    """

    def __init__(self, api_key: str, base_url: str, model: str, temperature: float = 0.0):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.temperature = temperature

    def score(self, paper: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        Score a single paper. Returns a dict with `match` (bool), `score` (float), `reason` (str).
        """
        summary = paper.get("abstract") or ""
        title = paper.get("title") or "Untitled"
        collections = ", ".join(paper.get("collections") or []) or "N/A"
        tags = ", ".join(paper.get("tags") or []) or "N/A"
        prompt = (
            "你是资深学术助手，需评估一篇论文与用户需求的相关性，并给出简短理由。\n"
            f"用户需求: {query}\n"
            "论文元信息：\n"
            f"- 标题: {title}\n"
            f"- 摘要: {summary}\n"
            f"- 标签: {tags}\n"
            f"- 集合: {collections}\n\n"
            "输出严格的 JSON（仅一行）：\n"
            '{"match": true/false, "score": 0.00, "reason": "中文理由，≤30字"}\n'
            "规则：\n"
            "- score 在 0-1，0=完全不相关或信息不足，1=高度契合；不确定时 score<=0.2 且 match=false。\n"
            "- 关注主题/方法/应用场景的匹配度，避免仅凭关键词。\n"
            "- reason 只写核心匹配/不匹配点，不要多余前后缀。"
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "Rate how relevant a paper is to the user request. Keep output as JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=self.temperature,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        try:
            parsed = json.loads(content)
            parsed["score"] = float(parsed.get("score", 0.0))
            parsed["match"] = bool(parsed.get("match", False))
            parsed["reason"] = str(parsed.get("reason", "")).strip()
            return parsed
        except Exception:
            # Fall back to a conservative default when parsing fails
            return {"match": False, "score": 0.0, "reason": "Failed to parse LLM response"}

    def translate(self, text: str, target_lang: str = "Chinese") -> str:
        """
        Translate a chunk of text using the same LLM endpoint.
        """
        if not text:
            return ""
        prompt = (
            f"请将以下摘要翻译为{target_lang}，直译为主，保持术语准确，避免添加说明，直接输出译文：\n\n{text}"
        )
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a concise scientific translator."},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return ""

    def summarize(self, title: str, abstract: str, target_lang: str = "Chinese", max_words: int = 80) -> str:
        """
        Generate a brief TLDR in the target language.
        """
        if not abstract:
            return ""
        prompt = (
            f"用{target_lang}写一个精炼 TLDR（约{max_words}词），突出任务、方法、关键贡献与主要结果，避免口水话：\n"
            f"标题: {title}\n"
            f"摘要: {abstract}"
        )
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a sharp academic summarizer."},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return ""
