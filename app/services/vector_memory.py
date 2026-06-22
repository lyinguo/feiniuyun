"""Long-term vector memory for story static facts and continuity anchors."""

from __future__ import annotations

import hashlib
import json
import math
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from app.config import settings
from app.services.memory_store import safe_component


@dataclass(frozen=True)
class VectorMemoryDocument:
    text: str
    kind: str
    chapter_title: str = ""
    source: str = "graph"
    metadata: dict[str, Any] | None = None


class VectorStoryMemory:
    """Small vector store wrapper.

    ChromaDB is used when installed. A deterministic local vector JSON fallback
    keeps the backend runnable in environments where Chroma has not been
    installed yet.
    """

    def __init__(self, base_dir: Path | None = None, dimensions: int = 256) -> None:
        self.base_dir = base_dir or settings.vector_memory_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.dimensions = dimensions
        self._lock = threading.RLock()
        self._chroma_collection = None
        self.backend = "json"
        self._init_chroma()

    def search(
        self,
        *,
        user_id: str,
        book_title: str,
        query: str,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        query = (query or "").strip()
        if not query:
            return []

        namespace = self._namespace(user_id, book_title)
        if self._chroma_collection is not None:
            return self._search_chroma(namespace, query, limit)
        return self._search_json(namespace, query, limit)

    def add_documents(
        self,
        *,
        user_id: str,
        book_title: str,
        documents: Iterable[VectorMemoryDocument],
    ) -> int:
        items = [item for item in documents if item.text.strip()]
        if not items:
            return 0

        namespace = self._namespace(user_id, book_title)
        if self._chroma_collection is not None:
            return self._add_chroma(namespace, items)
        return self._add_json(namespace, items)

    def add_graph_extracts(
        self,
        *,
        user_id: str,
        book_title: str,
        chapter_title: str,
        archivist_notes: dict[str, Any],
        summary_metadata: dict[str, Any] | None = None,
    ) -> int:
        docs: list[VectorMemoryDocument] = []

        background = archivist_notes.get("background") or {}
        for item in [*(background.get("new_settings") or []), *(background.get("updated_settings") or [])]:
            docs.append(
                VectorMemoryDocument(
                    text=self._setting_text(item),
                    kind="setting",
                    chapter_title=chapter_title,
                    metadata={"name": item.get("name", "")},
                )
            )
        for fact in background.get("canon_facts") or archivist_notes.get("canon_facts") or []:
            text = fact.get("fact") if isinstance(fact, dict) else str(fact)
            docs.append(VectorMemoryDocument(text=f"事实: {text}", kind="canon_fact", chapter_title=chapter_title))
        for note in background.get("visual_motifs") or []:
            docs.append(VectorMemoryDocument(text=f"视觉母题: {note}", kind="visual_motif", chapter_title=chapter_title))

        characters = archivist_notes.get("characters") or {}
        for item in [*(characters.get("new_characters") or []), *(characters.get("updated_characters") or [])]:
            docs.append(
                VectorMemoryDocument(
                    text=self._character_text(item),
                    kind="character",
                    chapter_title=chapter_title,
                    metadata={"name": item.get("name", "")},
                )
            )

        relationships = archivist_notes.get("relationships") or {}
        for item in relationships.get("relationships") or []:
            docs.append(
                VectorMemoryDocument(
                    text=(
                        f"人物关系: {item.get('source_name', '')} -> "
                        f"{item.get('target_name', '')}: {item.get('relation', '')}. "
                        f"证据: {item.get('evidence', '')}"
                    ),
                    kind="relationship",
                    chapter_title=chapter_title,
                )
            )

        casting = archivist_notes.get("casting") or {}
        for item in casting.get("choices") or []:
            docs.append(
                VectorMemoryDocument(
                    text=(
                        f"人物选型: {item.get('character_name', '')}; "
                        f"银幕类型: {item.get('screen_type', '')}; "
                        f"外貌锚点: {item.get('appearance_anchor', '')}; "
                        f"表演提示: {'; '.join(item.get('performance_notes') or [])}; "
                        f"妆造: {'; '.join(item.get('costume_or_makeup') or [])}"
                    ),
                    kind="casting",
                    chapter_title=chapter_title,
                )
            )

        summary = summary_metadata or {}
        for thread in summary.get("open_threads") or []:
            docs.append(VectorMemoryDocument(text=f"隐藏伏笔/未解线索: {thread}", kind="foreshadowing", chapter_title=chapter_title))
        for change in summary.get("character_state_changes") or []:
            docs.append(VectorMemoryDocument(text=f"人物状态变化: {change}", kind="character_state", chapter_title=chapter_title))

        return self.add_documents(user_id=user_id, book_title=book_title, documents=docs)

    def _init_chroma(self) -> None:
        try:
            import chromadb
        except Exception:
            return

        try:
            client = chromadb.PersistentClient(path=str(self.base_dir / "chroma"))
            self._chroma_collection = client.get_or_create_collection("story_long_term_memory")
            self.backend = "chroma"
        except Exception:
            self._chroma_collection = None
            self.backend = "json"

    def _add_chroma(self, namespace: str, items: list[VectorMemoryDocument]) -> int:
        # 🌟 核心改动：使用字典根据 doc_id 自动进行合并去重（后出现的覆盖先出现的）
        unique_items = {}
        for item in items:
            doc_id = self._doc_id(namespace, item)
            unique_items[doc_id] = item
        
        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []
        embeddings: list[list[float]] = []

        for doc_id, item in unique_items.items():
            ids.append(doc_id)
            documents.append(item.text)
            metadatas.append(self._metadata(namespace, item))
            embeddings.append(self._embed(item.text))

        with self._lock:
            self._chroma_collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings,
            )
        return len(items)

    def _search_chroma(self, namespace: str, query: str, limit: int) -> list[dict[str, Any]]:
        with self._lock:
            result = self._chroma_collection.query(
                query_embeddings=[self._embed(query)],
                n_results=max(1, limit),
                where={"namespace": namespace},
            )

        docs = result.get("documents") or [[]]
        metadatas = result.get("metadatas") or [[]]
        distances = result.get("distances") or [[]]
        output: list[dict[str, Any]] = []
        for text, metadata, distance in zip(docs[0], metadatas[0], distances[0]):
            output.append(
                {
                    "text": text,
                    "kind": (metadata or {}).get("kind", ""),
                    "chapter_title": (metadata or {}).get("chapter_title", ""),
                    "score": 1.0 / (1.0 + float(distance or 0.0)),
                }
            )
        return output

    def _add_json(self, namespace: str, items: list[VectorMemoryDocument]) -> int:
        path = self._json_path(namespace)
        with self._lock:
            records = self._read_json_records(path)
            by_id = {item["id"]: item for item in records}
            for item in items:
                doc_id = self._doc_id(namespace, item)
                by_id[doc_id] = {
                    "id": doc_id,
                    "text": item.text,
                    "embedding": self._embed(item.text),
                    "metadata": self._metadata(namespace, item),
                }
            path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = path.with_suffix(".tmp")
            temp_path.write_text(
                json.dumps(list(by_id.values()), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temp_path, path)
        return len(items)

    def _search_json(self, namespace: str, query: str, limit: int) -> list[dict[str, Any]]:
        path = self._json_path(namespace)
        query_embedding = self._embed(query)
        with self._lock:
            records = self._read_json_records(path)

        scored: list[tuple[float, dict[str, Any]]] = []
        for record in records:
            score = self._cosine(query_embedding, record.get("embedding") or [])
            scored.append((score, record))
        scored.sort(key=lambda item: item[0], reverse=True)
        output: list[dict[str, Any]] = []
        for score, record in scored[:limit]:
            metadata = record.get("metadata") or {}
            output.append(
                {
                    "text": record.get("text", ""),
                    "kind": metadata.get("kind", ""),
                    "chapter_title": metadata.get("chapter_title", ""),
                    "score": score,
                }
            )
        return output

    @staticmethod
    def _read_json_records(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        normalized = text.strip().lower()
        if not normalized:
            return vector

        tokens = self._tokens(normalized)
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(item * item for item in vector)) or 1.0
        return [item / norm for item in vector]

    @staticmethod
    def _tokens(text: str) -> list[str]:
        words = re_split_words(text)
        chars = [char for char in text if "\u4e00" <= char <= "\u9fff"]
        bigrams = [text[index : index + 2] for index in range(max(0, len(text) - 1))]
        return [*words, *chars, *bigrams[:600]]

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        if not left or not right:
            return 0.0
        size = min(len(left), len(right))
        return sum(left[index] * right[index] for index in range(size))

    @staticmethod
    def _namespace(user_id: str, book_title: str) -> str:
        user_raw = str(user_id or "unknown")
        book_raw = str(book_title or "unknown")
        user_hash = hashlib.sha1(user_raw.encode("utf-8")).hexdigest()[:8]
        book_hash = hashlib.sha1(book_raw.encode("utf-8")).hexdigest()[:12]
        return (
            f"{safe_component(user_raw)}_{user_hash}__"
            f"{safe_component(book_raw)}_{book_hash}"
        )

    def _json_path(self, namespace: str) -> Path:
        return self.base_dir / "json" / f"{namespace}.json"

    @staticmethod
    def _doc_id(namespace: str, item: VectorMemoryDocument) -> str:
        raw = f"{namespace}|{item.kind}|{item.chapter_title}|{item.text}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _metadata(namespace: str, item: VectorMemoryDocument) -> dict[str, Any]:
        metadata = item.metadata or {}
        return {
            "namespace": namespace,
            "kind": item.kind,
            "chapter_title": item.chapter_title,
            "source": item.source,
            "name": str(metadata.get("name", "")),
        }

    @staticmethod
    def _character_text(item: dict[str, Any]) -> str:
        relationships = []
        for relation in item.get("relationships") or []:
            if isinstance(relation, dict):
                relationships.append(
                    f"{relation.get('target_name', '')}:{relation.get('relation', '')}"
                )
        return (
            f"人物: {item.get('name', '')}; 别名: {'/'.join(item.get('aliases') or [])}; "
            f"外貌: {item.get('appearance', '')}; 性格: {'; '.join(item.get('personality') or [])}; "
            f"目标: {'; '.join(item.get('goals') or [])}; 关系: {'; '.join(relationships)}; "
            f"当前状态: {item.get('latest_state', '')}; 连续性: {'; '.join(item.get('continuity_notes') or [])}"
        )

    @staticmethod
    def _setting_text(item: dict[str, Any]) -> str:
        return (
            f"设定: {item.get('name', '')}; 类型: {item.get('category', '')}; "
            f"视觉: {item.get('visual_identity', '')}; 氛围: {item.get('atmosphere', '')}; "
            f"服装: {'; '.join(item.get('costume_notes') or [])}; "
            f"规则/机制: {'; '.join(item.get('rules_or_constraints') or [])}"
        )


def re_split_words(text: str) -> list[str]:
    import re

    return re.findall(r"[a-zA-Z0-9_]+", text)


vector_story_memory = VectorStoryMemory()
