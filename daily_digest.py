from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
import re
import shutil
import subprocess
from typing import Dict, Iterable, List, Optional

from PIL import Image
import requests

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - optional dependency at runtime
    PdfReader = None


_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


@dataclass
class DigestArtifact:
    markdown_path: Path
    assets_dir: Path
    papers: List[Dict]


def _slugify(value: str, fallback: str) -> str:
    text = (value or "").strip().lower()
    text = _NON_ALNUM_RE.sub("-", text).strip("-")
    return text[:64] or fallback


def _pdf_url(paper: Dict) -> Optional[str]:
    paper_id = (paper.get("id") or "").strip()
    if paper_id:
        return f"https://arxiv.org/pdf/{paper_id}.pdf"

    link = (paper.get("link") or paper.get("url") or "").strip()
    if not link:
        return None
    if "/abs/" in link:
        return link.replace("/abs/", "/pdf/") + ".pdf"
    if link.endswith(".pdf"):
        return link
    return None


def _download_pdf(pdf_url: str, pdf_path: Path) -> bool:
    response = requests.get(pdf_url, timeout=30)
    response.raise_for_status()
    pdf_path.write_bytes(response.content)
    return pdf_path.stat().st_size > 0


def _save_image(image: Image.Image, output_path: Path) -> Path:
    image = image.convert("RGB")
    image.save(output_path, format="PNG")
    return output_path


def _extract_embedded_image(pdf_path: Path, output_path: Path, max_pages: int) -> Optional[Path]:
    if PdfReader is None:
        return None

    try:
        reader = PdfReader(str(pdf_path))
    except Exception:
        return None

    for page in reader.pages[:max_pages]:
        images = getattr(page, "images", None) or []
        for image_file in images:
            try:
                image = Image.open(BytesIO(image_file.data))
                width, height = image.size
                if width < 200 or height < 200:
                    continue
                return _save_image(image, output_path)
            except Exception:
                continue
    return None


def _render_first_page_preview(pdf_path: Path, output_prefix: Path) -> Optional[Path]:
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        return None

    try:
        subprocess.run(
            [
                pdftoppm,
                "-f",
                "1",
                "-l",
                "1",
                "-png",
                str(pdf_path),
                str(output_prefix),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None

    return _find_preview_output(output_prefix)


def _find_preview_output(output_prefix: Path) -> Optional[Path]:
    candidates = sorted(output_prefix.parent.glob(f"{output_prefix.name}-*.png"))
    if not candidates:
        return None
    return candidates[0]


def extract_representative_figure(
    paper: Dict,
    assets_dir: Path,
    max_pages: int = 3,
) -> Optional[Path]:
    pdf_url = _pdf_url(paper)
    if not pdf_url:
        return None

    stem = _slugify(paper.get("id") or paper.get("title") or "paper", "paper")
    pdf_path = assets_dir / f"{stem}.pdf"
    figure_path = assets_dir / f"{stem}.png"
    preview_prefix = assets_dir / f"{stem}-preview"

    try:
        _download_pdf(pdf_url, pdf_path)
        embedded = _extract_embedded_image(pdf_path, figure_path, max_pages=max_pages)
        if embedded:
            return embedded

        preview = _render_first_page_preview(pdf_path, preview_prefix)
        if preview:
            if preview != figure_path:
                preview.replace(figure_path)
            for extra_preview in assets_dir.glob(f"{preview_prefix.name}-*.png"):
                if extra_preview != figure_path and extra_preview.exists():
                    extra_preview.unlink()
            return figure_path
    except Exception:
        return None
    finally:
        if pdf_path.exists():
            pdf_path.unlink()

    return None


def attach_figures(
    papers: Iterable[Dict],
    assets_dir: Path,
    enabled: bool = True,
    max_pages: int = 3,
) -> List[Dict]:
    assets_dir.mkdir(parents=True, exist_ok=True)
    enriched: List[Dict] = []
    for paper in papers:
        item = dict(paper)
        if enabled:
            figure_path = extract_representative_figure(item, assets_dir, max_pages=max_pages)
            if figure_path:
                item["figure_path"] = str(figure_path)
                item["figure_caption"] = "论文图像预览"
        enriched.append(item)
    return enriched


def _author_line(authors: List[str]) -> str:
    if not authors:
        return ""
    if len(authors) <= 6:
        return ", ".join(authors)
    return ", ".join(authors[:5] + ["...", authors[-1]])


def build_markdown_digest(
    title: str,
    query: str,
    papers: List[Dict],
    markdown_path: Path,
    generated_at: Optional[datetime] = None,
) -> str:
    generated_at = generated_at or datetime.now()
    lines = [
        f"# {title}",
        "",
        f"- 生成时间: {generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- arXiv 查询: `{query}`",
        f"- 论文数: {len(papers)}",
        "",
    ]

    if not papers:
        lines.extend(["暂无匹配论文。", ""])
        return "\n".join(lines)

    for idx, paper in enumerate(papers, start=1):
        link = paper.get("link") or paper.get("url") or ""
        score = paper.get("score")
        score_text = f"{score:.2f}" if isinstance(score, (int, float)) else "N/A"
        lines.append(f"## {idx}. {paper.get('title', 'Untitled')}")
        lines.append("")
        if link:
            lines.append(f"- 链接: {link}")
        lines.append(f"- 相关度: {score_text}")

        authors = _author_line(paper.get("authors") or [])
        if authors:
            lines.append(f"- 作者: {authors}")

        tags = paper.get("tags") or []
        if tags:
            lines.append(f"- 关键词: {', '.join(tags[:8])}")

        tldr = (paper.get("tldr") or "").strip()
        if tldr:
            lines.append(f"- TLDR: {tldr}")

        abstract_zh = (paper.get("abstract_zh") or "").strip()
        abstract = (paper.get("abstract") or "").strip()
        if abstract_zh:
            lines.append("")
            lines.append("### 中文摘要")
            lines.append("")
            lines.append(abstract_zh)
        elif abstract:
            lines.append("")
            lines.append("### 摘要")
            lines.append("")
            lines.append(abstract)

        figure_path = paper.get("figure_path")
        if figure_path:
            relative_path = Path(figure_path).relative_to(markdown_path.parent)
            caption = paper.get("figure_caption") or "论文相关图像"
            lines.append("")
            lines.append(f"![{caption}]({relative_path.as_posix()})")

        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def generate_daily_digest(
    title: str,
    query: str,
    papers: List[Dict],
    output_root: str = "output/digests",
    include_figures: bool = True,
    figure_pages: int = 3,
    generated_at: Optional[datetime] = None,
) -> DigestArtifact:
    generated_at = generated_at or datetime.now()
    date_dir = generated_at.strftime("%Y-%m-%d")
    root = Path(output_root) / date_dir
    assets_dir = root / "assets"
    root.mkdir(parents=True, exist_ok=True)

    enriched = attach_figures(
        papers=papers,
        assets_dir=assets_dir,
        enabled=include_figures,
        max_pages=figure_pages,
    )

    markdown_path = root / "daily_digest.md"
    markdown = build_markdown_digest(
        title=title,
        query=query,
        papers=enriched,
        markdown_path=markdown_path,
        generated_at=generated_at,
    )
    markdown_path.write_text(markdown, encoding="utf-8")

    return DigestArtifact(markdown_path=markdown_path, assets_dir=assets_dir, papers=enriched)
