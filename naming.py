from __future__ import annotations

from datetime import datetime


def build_daily_doc_title(base_title: str, generated_at: datetime) -> str:
    base = (base_title or "每日论文推送").strip()
    date_prefix = generated_at.strftime("%Y-%m-%d")
    if base.startswith(date_prefix):
        return base
    return f"{date_prefix} {base}"
