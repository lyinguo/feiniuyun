"""Novel chapter splitting and batching."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List


@dataclass(frozen=True)
class Chapter:
    index: int
    title: str
    text: str
    auto_generated: bool = False
    start_line: int | None = None
    end_line: int | None = None

    @property
    def chapter_id(self) -> str:
        return f"ch{self.index:03d}"


class ChapterSplitter:
    """Split Chinese or English novel text into chapters.

    The splitter prefers explicit headings. If a manuscript has no headings it
    can create length-based chunks, but the API still reports that as a warning
    because automatic chunks are weaker source references.
    """

    heading_pattern = re.compile(
        r"^\s*(?:#{1,3}\s*)?"
        r"((?:第\s*[零〇一二两三四五六七八九十百千万\d]+\s*[章节回幕卷部]"
        r"(?:\s*[^\n]{0,40})?)|(?:chapter\s+\d+(?:[:：\s-][^\n]{0,40})?))\s*$",
        re.IGNORECASE,
    )

    def __init__(self, fallback_chunk_chars: int = 3500):
        self.fallback_chunk_chars = fallback_chunk_chars

    def split(self, raw_text: str) -> List[Chapter]:
        text = self._normalize(raw_text)
        if not text:
            return []

        lines = text.split("\n")
        markers: list[tuple[int, str]] = []
        for line_index, line in enumerate(lines):
            trimmed = line.strip()
            if len(trimmed) <= 80 and self.heading_pattern.match(trimmed):
                markers.append((line_index, trimmed.lstrip("#").strip()))

        if len(markers) >= 2:
            chapters: list[Chapter] = []
            for index, (marker_line, title) in enumerate(markers, start=1):
                next_line = markers[index][0] if index < len(markers) else len(lines)
                chapter_text = "\n".join(lines[marker_line + 1 : next_line]).strip()
                if chapter_text:
                    chapters.append(
                        Chapter(
                            index=len(chapters) + 1,
                            title=title,
                            text=chapter_text,
                            auto_generated=False,
                            start_line=marker_line + 2,
                            end_line=next_line,
                        )
                    )
            return chapters

        return self._split_by_length(text)

    def batches(self, chapters: Iterable[Chapter], batch_size: int) -> list[list[Chapter]]:
        items = list(chapters)
        size = max(1, batch_size)
        return [items[offset : offset + size] for offset in range(0, len(items), size)]

    def _split_by_length(self, text: str) -> List[Chapter]:
        paragraphs = [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
        chunks: list[str] = []
        current: list[str] = []
        current_size = 0

        for paragraph in paragraphs:
            if current and current_size + len(paragraph) > self.fallback_chunk_chars:
                chunks.append("\n\n".join(current))
                current = []
                current_size = 0
            current.append(paragraph)
            current_size += len(paragraph)

        if current:
            chunks.append("\n\n".join(current))

        if len(chunks) <= 1 and len(text) > self.fallback_chunk_chars:
            chunks = [
                text[offset : offset + self.fallback_chunk_chars]
                for offset in range(0, len(text), self.fallback_chunk_chars)
            ]

        return [
            Chapter(
                index=index + 1,
                title=f"自动分章 {index + 1}",
                text=chunk,
                auto_generated=True,
            )
            for index, chunk in enumerate(chunks)
            if chunk.strip()
        ]

    @staticmethod
    def _normalize(raw_text: str) -> str:
        return (
            str(raw_text or "")
            .replace("\r\n", "\n")
            .replace("\r", "\n")
            .replace("\u3000", " ")
            .strip()
        )


chapter_splitter = ChapterSplitter()
