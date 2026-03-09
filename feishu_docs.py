from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import time
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlparse

from PIL import Image
import requests


@dataclass
class FeishuDocResult:
    document_id: str
    document_url: str
    wiki_node_token: str = ""
    wiki_url: str = ""
    parent_node_token: str = ""


class FeishuDocsClient:
    ABSTRACT_TEXT_COLOR = 7

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        wiki_parent_url: str = "",
        update_parent_doc: bool = True,
        base_url: str = "https://open.feishu.cn",
        doc_base_url: str = "",
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.wiki_parent_url = wiki_parent_url
        self.update_parent_doc = update_parent_doc
        self.base_url = base_url.rstrip("/")
        self.doc_base_url = self._resolve_doc_base_url(doc_base_url=doc_base_url, wiki_parent_url=wiki_parent_url)
        self._tenant_access_token: Optional[str] = None

    @staticmethod
    def _resolve_doc_base_url(doc_base_url: str, wiki_parent_url: str) -> str:
        explicit = (doc_base_url or "").strip()
        if explicit:
            return explicit.rstrip("/")

        parsed = urlparse((wiki_parent_url or "").strip())
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"

        return "https://feishu.cn"

    def _request(self, method: str, path: str, **kwargs) -> Dict:
        headers = kwargs.pop("headers", {})
        if self._tenant_access_token:
            headers["Authorization"] = f"Bearer {self._tenant_access_token}"
        last_error: Optional[RuntimeError] = None
        for attempt in range(5):
            response = requests.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                timeout=30,
                **kwargs,
            )
            try:
                payload = response.json()
            except ValueError:
                payload = None

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                try:
                    sleep_seconds = float(retry_after) if retry_after else min(2 ** attempt, 8)
                except ValueError:
                    sleep_seconds = min(2 ** attempt, 8)
                last_error = RuntimeError(
                    f"Feishu HTTP error for {path}: status=429, detail={payload if payload is not None else response.text}"
                )
                time.sleep(sleep_seconds)
                continue

            if response.status_code >= 500:
                last_error = RuntimeError(
                    f"Feishu HTTP error for {path}: status={response.status_code}, detail={payload if payload is not None else response.text}"
                )
                time.sleep(min(2 ** attempt, 8))
                continue

            if response.status_code >= 400:
                detail = payload if payload is not None else response.text
                raise RuntimeError(
                    f"Feishu HTTP error for {path}: status={response.status_code}, detail={detail}"
                )

            if payload is None:
                raise RuntimeError(
                    f"Feishu API returned non-JSON response for {path}: {response.text}"
                )
            if payload.get("code", 0) not in (0, "0"):
                raise RuntimeError(
                    f"Feishu API failed for {path}: code={payload.get('code')} msg={payload.get('msg')} payload={payload}"
                )
            return payload

        raise last_error or RuntimeError(f"Feishu request failed after retries for {path}")

    def ensure_token(self) -> str:
        if self._tenant_access_token:
            return self._tenant_access_token

        payload = self._request(
            "POST",
            "/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
        )
        token = payload.get("tenant_access_token")
        if not token:
            raise RuntimeError("Feishu tenant access token missing in auth response")
        self._tenant_access_token = token
        return token

    @staticmethod
    def extract_wiki_token(value: str) -> str:
        text = (value or "").strip()
        if not text:
            return ""
        if text.startswith("http://") or text.startswith("https://"):
            parsed = urlparse(text)
            parts = [part for part in parsed.path.split("/") if part]
            if "wiki" in parts:
                idx = parts.index("wiki")
                if idx + 1 < len(parts):
                    return parts[idx + 1]
            return ""
        return text

    def _browser_url(self, path: str) -> str:
        return f"{self.doc_base_url.rstrip('/')}/{path.lstrip('/')}"

    def get_wiki_node(self, token_or_url: str) -> Dict:
        self.ensure_token()
        token = self.extract_wiki_token(token_or_url)
        if not token:
            raise RuntimeError("Wiki parent token is empty")

        payload = self._request(
            "GET",
            "/open-apis/wiki/v2/spaces/get_node",
            params={"token": token},
        )
        data = payload.get("data", {})
        node = data.get("node", data)
        if not node.get("node_token"):
            node["node_token"] = token
        return node

    def create_wiki_child_document(self, title: str, parent_node: Dict) -> FeishuDocResult:
        self.ensure_token()
        space_id = parent_node.get("space_id")
        parent_node_token = parent_node.get("node_token")
        if not space_id or not parent_node_token:
            raise RuntimeError("Wiki parent node is missing space_id or node_token")

        payload = self._request(
            "POST",
            f"/open-apis/wiki/v2/spaces/{space_id}/nodes",
            json={
                "parent_node_token": parent_node_token,
                "node_type": "origin",
                "obj_type": "docx",
                "title": title,
            },
        )
        data = payload.get("data", {})
        node = data.get("node", data)
        node_token = node.get("node_token") or data.get("node_token")
        obj_token = node.get("obj_token") or data.get("obj_token")
        if not node_token or not obj_token:
            raise RuntimeError("Feishu create wiki node response missing node/doc token")

        wiki_url = self._browser_url(f"wiki/{node_token}")
        return FeishuDocResult(
            document_id=obj_token,
            document_url=wiki_url,
            wiki_node_token=node_token,
            wiki_url=wiki_url,
            parent_node_token=parent_node_token,
        )

    def append_blocks(self, document_id: str, blocks: Iterable[Dict]) -> None:
        self.ensure_token()
        block_list = list(blocks)
        pending_text_blocks: List[Dict] = []
        for block in block_list:
            if block.get("block_type") == 27:
                self._flush_text_blocks(document_id=document_id, blocks=pending_text_blocks)
                pending_text_blocks = []
                created_block_id = self._create_child_block(document_id=document_id, parent_block_id=document_id, block=block)
                local_image_path = block.get("_local_image_path")
                if local_image_path and created_block_id:
                    image_token = self.upload_image(document_id=created_block_id, image_path=local_image_path)
                    self.replace_image(document_id=document_id, block_id=created_block_id, image_token=image_token)
                continue

            pending_text_blocks.append(block)
            if len(pending_text_blocks) >= 20:
                self._flush_text_blocks(document_id=document_id, blocks=pending_text_blocks)
                pending_text_blocks = []

        self._flush_text_blocks(document_id=document_id, blocks=pending_text_blocks)

    def _flush_text_blocks(self, document_id: str, blocks: List[Dict]) -> None:
        if not blocks:
            return
        self._create_child_blocks(document_id=document_id, parent_block_id=document_id, blocks=blocks)

    @staticmethod
    def _public_block_payload(block: Dict) -> Dict:
        return {key: value for key, value in block.items() if not key.startswith("_")}

    def _create_child_block(self, document_id: str, parent_block_id: str, block: Dict) -> str:
        block_ids = self._create_child_blocks(document_id=document_id, parent_block_id=parent_block_id, blocks=[block])
        return block_ids[0] if block_ids else ""

    def _create_child_blocks(self, document_id: str, parent_block_id: str, blocks: List[Dict]) -> List[str]:
        payload = self._request(
            "POST",
            f"/open-apis/docx/v1/documents/{document_id}/blocks/{parent_block_id}/children",
            json={"children": [self._public_block_payload(block) for block in blocks]},
        )
        data = payload.get("data", {})
        children = data.get("children") or data.get("items") or []
        if not children and data.get("block"):
            children = [data.get("block")]
        block_ids: List[str] = []
        for child in children:
            block_id = child.get("block_id") or child.get("blockId") or child.get("block_token") or ""
            if block_id:
                block_ids.append(block_id)
        return block_ids

    def upload_image(self, document_id: str, image_path: str) -> str:
        self.ensure_token()
        path = Path(image_path)
        with path.open("rb") as file_obj:
            payload = self._request(
                "POST",
                "/open-apis/drive/v1/medias/upload_all",
                data={
                    "file_name": path.name,
                    "parent_type": "docx_image",
                    "parent_node": document_id,
                    "size": str(path.stat().st_size),
                },
                files={"file": (path.name, file_obj, "image/png")},
            )

        data = payload.get("data", {})
        image_token = (
            data.get("file_token")
            or data.get("token")
            or data.get("media", {}).get("file_token")
            or data.get("media", {}).get("token")
        )
        if not image_token:
            raise RuntimeError("Feishu upload image response missing token")
        return image_token

    def replace_image(self, document_id: str, block_id: str, image_token: str) -> None:
        self.ensure_token()
        self._request(
            "PATCH",
            f"/open-apis/docx/v1/documents/{document_id}/blocks/{block_id}",
            json={"replace_image": {"token": image_token}},
        )

    def _text_elements(self, content: str, *, text_color: Optional[int] = None, italic: bool = False) -> List[Dict]:
        style: Dict = {}
        if text_color is not None:
            style["text_color"] = text_color
        if italic:
            style["italic"] = True
        text_run: Dict = {"content": content}
        if style:
            text_run["text_element_style"] = style
        return [{"text_run": text_run}]

    def _paragraph_block(
        self,
        content: str,
        *,
        text_color: Optional[int] = None,
        italic: bool = False,
    ) -> Dict:
        return {
            "block_type": 2,
            "text": {
                "elements": self._text_elements(content, text_color=text_color, italic=italic),
            },
        }

    def _heading1_block(self, content: str) -> Dict:
        return {
            "block_type": 3,
            "heading1": {
                "elements": self._text_elements(content),
            },
        }

    def _heading2_block(self, content: str) -> Dict:
        return {
            "block_type": 4,
            "heading2": {
                "elements": self._text_elements(content),
            },
        }

    def _image_block(self, image_token: str, width: int, height: int) -> Dict:
        return {
            "block_type": 27,
            "image": {},
            "_local_image_path": image_token,
            "_image_width": width,
            "_image_height": height,
        }

    def build_blocks(
        self,
        title: str,
        query: str,
        papers: List[Dict],
        document_id: str,
    ) -> List[Dict]:
        blocks: List[Dict] = [
            self._paragraph_block(f"arXiv 查询: {query}"),
            self._paragraph_block(f"论文数: {len(papers)}"),
        ]

        if not papers:
            blocks.append(self._paragraph_block("暂无匹配论文。"))
            return blocks

        for idx, paper in enumerate(papers, start=1):
            blocks.append(self._heading2_block(f"{idx}. {paper.get('title', 'Untitled')}"))

            link = paper.get("link") or paper.get("url")
            if link:
                blocks.append(self._paragraph_block(f"链接: {link}"))

            score = paper.get("score")
            score_text = f"{score:.2f}" if isinstance(score, (int, float)) else "N/A"
            blocks.append(self._paragraph_block(f"相关度: {score_text}"))

            authors = paper.get("authors") or []
            if authors:
                blocks.append(self._paragraph_block("作者: " + ", ".join(authors[:8])))

            tags = paper.get("tags") or []
            if tags:
                blocks.append(self._paragraph_block("关键词: " + ", ".join(tags[:8])))

            tldr = (paper.get("tldr") or "").strip()
            if tldr:
                blocks.append(self._paragraph_block("TLDR: " + tldr))

            abstract = (paper.get("abstract") or "").strip()
            abstract_zh = (paper.get("abstract_zh") or "").strip()
            if abstract:
                blocks.append(self._paragraph_block("Abstract:", text_color=self.ABSTRACT_TEXT_COLOR, italic=True))
                blocks.append(self._paragraph_block(abstract, text_color=self.ABSTRACT_TEXT_COLOR))
            elif abstract_zh:
                blocks.append(
                    self._paragraph_block(
                        "Abstract (ZH fallback):",
                        text_color=self.ABSTRACT_TEXT_COLOR,
                        italic=True,
                    )
                )
                blocks.append(self._paragraph_block(abstract_zh, text_color=self.ABSTRACT_TEXT_COLOR))

            figure_path = paper.get("figure_path")
            if figure_path:
                with Image.open(figure_path) as image:
                    width, height = image.size
                blocks.append(self._image_block(figure_path, width, height))

        return blocks

    def append_parent_index_entry(
        self,
        parent_node: Dict,
        child_title: str,
        child_url: str,
        generated_at: Optional[datetime] = None,
    ) -> None:
        if not self.update_parent_doc:
            return

        parent_obj_type = (parent_node.get("obj_type") or "").lower()
        parent_doc_token = parent_node.get("obj_token") or ""
        if parent_obj_type != "docx" or not parent_doc_token:
            return

        generated_at = generated_at or datetime.now()
        lines = [
            self._heading2_block(generated_at.strftime("%Y-%m-%d 日报")),
            self._paragraph_block(child_title),
            self._paragraph_block(child_url),
        ]
        self.append_blocks(document_id=parent_doc_token, blocks=lines)

    def publish_digest(
        self,
        title: str,
        query: str,
        papers: List[Dict],
        generated_at: Optional[datetime] = None,
    ) -> FeishuDocResult:
        generated_at = generated_at or datetime.now()

        if not self.wiki_parent_url:
            raise RuntimeError("Wiki parent is required. Set feishu.parent_url.")

        parent_node = self.get_wiki_node(self.wiki_parent_url)
        document = self.create_wiki_child_document(title=title, parent_node=parent_node)
        blocks = self.build_blocks(
            title=title,
            query=query,
            papers=papers,
            document_id=document.document_id,
        )
        self.append_blocks(document_id=document.document_id, blocks=blocks)
        self.append_parent_index_entry(
            parent_node=parent_node,
            child_title=title,
            child_url=document.document_url,
            generated_at=generated_at,
        )
        return document
