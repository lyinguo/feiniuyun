"""File-project screenplay workflow built on top of the LangGraph runner."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.agent.script_graph.workflow import load_template_schema, run_chapter
from app.models.request import ConvertProjectRequest
from app.services.chapter_splitter import Chapter
from app.services.memory_store import memory_store, new_memory, safe_component


class ScriptProjectError(RuntimeError):
    """Raised for user-visible file-project workflow failures."""


@dataclass(frozen=True)
class SourceUnit:
    """One model-sized unit read from a project metadata file."""

    unit_index: int
    logical_index: int
    logical_title: str
    source_file: str
    source_part: int
    source_part_count: int
    text: str

    @property
    def display_title(self) -> str:
        if self.source_part_count <= 1:
            return self.logical_title
        return f"{self.logical_title}（分段 {self.source_part}/{self.source_part_count}）"


class ScriptProjectService:
    """Run a metadata.json + chapter txt project through the graph.

    The source format is the one produced under ``data/temp_epubs``:
    a folder containing one metadata.json and multiple chapter/chunk txt files.
    """

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        output_root: Path | None = None,
    ) -> None:
        self.project_root = project_root or Path("data/temp_epubs")
        self.output_root = output_root or Path("data/script_outputs")

    def list_projects(self) -> list[dict[str, Any]]:
        projects: list[dict[str, Any]] = []
        root = self.project_root
        if not root.exists():
            return projects

        for metadata_path in sorted(root.glob("*/metadata.json")):
            try:
                metadata = self._read_json(metadata_path)
            except ScriptProjectError:
                continue
            chapters = metadata.get("chapters") or []
            projects.append(
                {
                    "project_path": metadata_path.parent.name,
                    "book_title": metadata.get("book_title") or metadata_path.parent.name,
                    "chapter_count": len(chapters),
                    "source_file_count": self._count_source_files(chapters),
                    "total_char_count": metadata.get("total_char_count", 0),
                    "metadata_path": str(metadata_path.as_posix()),
                }
            )
        return projects

    async def run_project(self, request: ConvertProjectRequest) -> dict[str, Any]:
        final_data: dict[str, Any] | None = None
        async for event in self.stream_project_events(request):
            if event.get("event") == "done":
                final_data = event["data"]
        if final_data is None:
            raise ScriptProjectError("项目生成没有产生最终结果。")
        return final_data

    async def stream_project_events(self, request: ConvertProjectRequest, send_event_callback=None):
        project_dir = self._resolve_project_dir(request.project_path)
        metadata = self._read_json(project_dir / "metadata.json")
        book_title = request.title or metadata.get("book_title") or project_dir.name
        units = self._load_units(project_dir, metadata, request)
        if not units:
            raise ScriptProjectError("项目中没有可处理的 txt 正文。")

        output_dir = self._make_output_dir(request, book_title)
        output_dir.mkdir(parents=True, exist_ok=True)

        yield {
            "event": "start",
            "book_title": book_title,
            "project_path": request.project_path,
            "unit_count": len(units),
            "output_dir": str(output_dir.as_posix()),
        }

        memory = memory_store.load(
            request.user_id,
            request.thread_id,
            request.short_term_window,
        )
        if self._memory_has_content(memory) and memory.get("book_title") != book_title:
            memory = new_memory(
                request.user_id,
                request.thread_id,
                request.short_term_window,
            )
        memory["book_title"] = book_title
        memory.setdefault("long_term", {})["book_title"] = book_title
        rolling_summary = self._seed_rolling_summary(memory)
        global_characters = self._seed_records(memory, "characters")
        global_settings = self._seed_records(memory, "locations")
        previous_chapter_summaries = self._seed_previous_chapter_summaries(memory)
        template_schema = load_template_schema()

        acts: list[dict[str, Any]] = []
        total_scene_count = 0
        for unit in units:
            yield {
                "event": "unit_start",
                "unit_index": unit.unit_index,
                "unit_count": len(units),
                "chapter_title": unit.display_title,
                "source_file": unit.source_file,
                "source_char_count": len(unit.text),
            }

            result = await run_chapter(
                Chapter(
                    index=unit.unit_index,
                    title=unit.display_title,
                    text=unit.text,
                    auto_generated=unit.source_part_count > 1,
                ),
                rolling_summary=rolling_summary,
                global_characters=global_characters,
                global_settings=global_settings,
                user_id=request.user_id,
                book_title=book_title,
                previous_chapter_summaries=previous_chapter_summaries,
                template_schema=template_schema,
                scene_density=request.scene_density,
                max_retries=request.max_retries,
                send_event_callback=send_event_callback,
            )

            rolling_summary = result.get("rolling_summary", rolling_summary)
            global_characters = result.get("global_characters", global_characters)
            global_settings = result.get("global_settings", global_settings)
            script_data = result.get("current_script_data") or {}
            plot_text = self._render_plot_text(unit, script_data, result)
            output_name = f"plot_{unit.unit_index:04d}.txt"
            output_path = output_dir / output_name
            output_path.write_text(plot_text, encoding="utf-8")

            scene_count = len(script_data.get("scenes") or [])
            total_scene_count += scene_count
            act = {
                "act_id": f"act_{unit.unit_index:04d}",
                "logical_chapter_index": unit.logical_index,
                "chapter_title": unit.logical_title,
                "source_file": unit.source_file,
                "source_part": unit.source_part,
                "source_part_count": unit.source_part_count,
                "txt_file": output_name,
                "txt_char_count": len(plot_text),
                "source_char_count": len(unit.text),
                "scene_count": scene_count,
                "chapter_summary": script_data.get("chapter_summary", ""),
                "rolling_summary_after": rolling_summary,
                "character_introductions": self._character_introductions(script_data),
                "critic_warnings": result.get("critic_warnings", []),
                "continuity_warnings": result.get("continuity_warnings", []),
                "continuity_review": result.get("continuity_review", {}),
                "error_msg": result.get("error_msg", ""),
                "retry_count": result.get("retry_count", 0),
                "retrieved_memory_count": len(result.get("retrieved_memories") or []),
                "vector_memory_writes": result.get("vector_memory_writes", 0),
                "canon_facts": (result.get("archivist_notes") or {}).get("canon_facts", []),
                "open_threads": (
                    (result.get("archivist_notes") or {})
                    .get("latest_summary_metadata", {})
                    .get("open_threads", [])
                ),
            }
            acts.append(act)
            previous_chapter_summaries.append(
                {
                    "chapter_index": unit.unit_index,
                    "chapter_title": unit.display_title,
                    "summary": script_data.get("chapter_summary", ""),
                    "rolling_summary_after": rolling_summary,
                }
            )
            yield {
                "event": "unit_done",
                "unit_index": unit.unit_index,
                "unit_count": len(units),
                "act": act,
                "plot_text": plot_text,
                "rolling_summary": rolling_summary,
                "stats": {
                    "processed_unit_count": len(acts),
                    "scene_count": total_scene_count,
                    "source_char_count": sum(item["source_char_count"] for item in acts),
                    "output_txt_count": len(acts),
                },
            }

        manifest = {
            "schema_version": "1.0",
            "book_title": book_title,
            "user_id": request.user_id,
            "thread_id": request.thread_id,
            "target_format": request.target_format,
            "adaptation_tone": request.adaptation_tone,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source_project": str(project_dir.as_posix()),
            "output_dir": str(output_dir.as_posix()),
            "rolling_summary": rolling_summary,
            "global_characters": global_characters,
            "global_settings": global_settings,
            "template_schema_path": "template.yaml",
            "acts": acts,
            "stats": {
                "logical_chapter_count": len({item.logical_index for item in units}),
                "processed_unit_count": len(units),
                "scene_count": total_scene_count,
                "source_char_count": sum(len(item.text) for item in units),
                "output_txt_count": len(acts),
            },
        }
        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._save_memory(
            request=request,
            memory=memory,
            rolling_summary=rolling_summary,
            global_characters=global_characters,
            global_settings=global_settings,
            acts=acts,
        )

        data = {
            "project": {
                "book_title": book_title,
                "project_path": request.project_path,
            },
            "output_dir": str(output_dir.as_posix()),
            "manifest_path": str(manifest_path.as_posix()),
            "manifest": manifest,
            "stats": manifest["stats"],
        }
        yield {
            "event": "done",
            "data": data,
        }

    def _resolve_project_dir(self, value: str) -> Path:
        root = self.project_root.resolve()
        raw = Path(value)
        candidate = raw if raw.is_absolute() else root / raw
        if candidate.is_file():
            candidate = candidate.parent
        resolved = candidate.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ScriptProjectError("project_path 必须位于 data/temp_epubs 目录内。") from exc
        if not (resolved / "metadata.json").exists():
            raise ScriptProjectError("未找到 metadata.json，请选择已拆分的小说项目目录。")
        return resolved

    def _load_units(
        self,
        project_dir: Path,
        metadata: dict[str, Any],
        request: ConvertProjectRequest,
    ) -> list[SourceUnit]:
        chapters = list(metadata.get("chapters") or [])
        if request.max_chapters:
            chapters = chapters[: request.max_chapters]

        units: list[SourceUnit] = []
        for chapter in chapters:
            logical_index = int(chapter.get("logical_index", len(units)))
            title = chapter.get("original_title") or f"第 {logical_index + 1} 章"
            refs = self._chapter_file_refs(chapter)
            for file_ref in refs:
                source_path = self._resolve_source_file(project_dir, file_ref)
                text = source_path.read_text(encoding="utf-8").strip()
                if not text:
                    continue
                parts = self._split_text(text, request.max_chunk_chars)
                for part_index, part_text in enumerate(parts, start=1):
                    units.append(
                        SourceUnit(
                            unit_index=len(units) + 1,
                            logical_index=logical_index,
                            logical_title=title,
                            source_file=source_path.name,
                            source_part=part_index,
                            source_part_count=len(parts),
                            text=part_text,
                        )
                    )
                    if request.max_units and len(units) >= request.max_units:
                        return units
        return units

    @staticmethod
    def _chapter_file_refs(chapter: dict[str, Any]) -> list[str]:
        if chapter.get("is_chunked"):
            chunks = sorted(chapter.get("chunks") or [], key=lambda item: item.get("sub_index", 0))
            return [item["file_path"] for item in chunks if item.get("file_path")]
        file_path = chapter.get("file_path")
        return [file_path] if file_path else []

    def _resolve_source_file(self, project_dir: Path, file_ref: str) -> Path:
        source_path = (project_dir / file_ref).resolve()
        try:
            source_path.relative_to(project_dir.resolve())
        except ValueError as exc:
            raise ScriptProjectError(f"章节文件越界：{file_ref}") from exc
        if not source_path.exists():
            raise ScriptProjectError(f"章节文件不存在：{file_ref}")
        return source_path

    @staticmethod
    def _split_text(text: str, max_chars: int) -> list[str]:
        if len(text) <= max_chars:
            return [text]

        paragraphs = [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
        chunks: list[str] = []
        current: list[str] = []
        current_size = 0

        def flush() -> None:
            nonlocal current, current_size
            if current:
                chunks.append("\n\n".join(current).strip())
                current = []
                current_size = 0

        for paragraph in paragraphs:
            if len(paragraph) > max_chars:
                flush()
                chunks.extend(
                    paragraph[offset : offset + max_chars].strip()
                    for offset in range(0, len(paragraph), max_chars)
                    if paragraph[offset : offset + max_chars].strip()
                )
                continue
            next_size = current_size + len(paragraph) + (2 if current else 0)
            if current and next_size > max_chars:
                flush()
            current.append(paragraph)
            current_size += len(paragraph) + (2 if current_size else 0)
        flush()
        return chunks

    def _make_output_dir(self, request: ConvertProjectRequest, book_title: str) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder = f"{safe_component(book_title)}_{safe_component(request.thread_id)}_{stamp}"
        return self.output_root / safe_component(request.user_id) / folder

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ScriptProjectError(f"文件不存在：{path}") from exc
        except json.JSONDecodeError as exc:
            raise ScriptProjectError(f"JSON 解析失败：{path}") from exc

    @staticmethod
    def _count_source_files(chapters: list[dict[str, Any]]) -> int:
        count = 0
        for chapter in chapters:
            if chapter.get("is_chunked"):
                count += len(chapter.get("chunks") or [])
            elif chapter.get("file_path"):
                count += 1
        return count

    @staticmethod
    def _seed_rolling_summary(memory: dict[str, Any]) -> str:
        long_term = memory.get("long_term", {})
        lines = [long_term.get("logline", "").strip()]
        recent = memory.get("short_term", {}).get("recent_chapters", [])
        lines.extend(item.get("summary", "").strip() for item in recent[-3:] if item.get("summary"))
        return "\n".join(item for item in lines if item)

    @staticmethod
    def _memory_has_content(memory: dict[str, Any]) -> bool:
        long_term = memory.get("long_term", {})
        short_term = memory.get("short_term", {})
        return bool(
            long_term.get("logline")
            or long_term.get("characters")
            or long_term.get("locations")
            or long_term.get("canon_facts")
            or long_term.get("unresolved_threads")
            or short_term.get("recent_chapters")
        )

    @staticmethod
    def _seed_records(memory: dict[str, Any], key: str) -> list[dict[str, Any]]:
        raw = memory.get("long_term", {}).get(key, {})
        if isinstance(raw, dict):
            return [item for item in raw.values() if isinstance(item, dict)]
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
        return []

    @staticmethod
    def _seed_previous_chapter_summaries(memory: dict[str, Any]) -> list[dict[str, Any]]:
        recent = memory.get("short_term", {}).get("recent_chapters", [])
        return [
            {
                "chapter_index": index,
                "chapter_title": item.get("title", ""),
                "summary": item.get("summary", ""),
            }
            for index, item in enumerate(recent, start=1)
            if isinstance(item, dict) and item.get("summary")
        ]

    @staticmethod
    def _render_plot_text(
        unit: SourceUnit,
        script_data: dict[str, Any],
        result: dict[str, Any],
    ) -> str:
        yaml_text = (result.get("current_script_yaml") or "").strip()
        if yaml_text:
            return yaml_text + "\n"

        lines = [
            f"标题：{unit.display_title}",
            f"来源文件：{unit.source_file}",
            "",
            f"本段一句话：{script_data.get('chapter_logline', '')}",
            "",
            "剧情摘要：",
            script_data.get("chapter_summary", ""),
            "",
            "场景：",
        ]
        for index, scene in enumerate(script_data.get("scenes") or [], start=1):
            slugline = scene.get("slugline") or {}
            lines.extend(
                [
                    "",
                    f"{index}. {scene.get('title', '未命名场景')}",
                    f"场景头：{slugline.get('location', '未标明地点')} / {slugline.get('time', 'unknown')} / {slugline.get('space', 'unknown')}",
                    f"戏剧目的：{scene.get('purpose', '')}",
                    f"冲突：{scene.get('conflict', '')}",
                    f"出场人物：{'、'.join(scene.get('characters') or [])}",
                    "动作：",
                ]
            )
            lines.extend(f"- {item}" for item in scene.get("action") or [])
            dialogue = scene.get("dialogue") or []
            if dialogue:
                lines.append("对白：")
                lines.extend(f"- {item.get('speaker', '')}：{item.get('line', '')}" for item in dialogue)
            if scene.get("revision_note"):
                lines.append(f"修订提示：{scene.get('revision_note')}")

        warnings = result.get("critic_warnings") or []
        if warnings:
            lines.extend(["", "审查提醒：", *[f"- {item}" for item in warnings]])
        if result.get("error_msg"):
            lines.extend(["", f"未完全解决的问题：{result.get('error_msg')}"])
        return "\n".join(lines).strip() + "\n"

    @staticmethod
    def _character_introductions(script_data: dict[str, Any]) -> list[dict[str, Any]]:
        usage = {
            item.get("name"): {
                "name": item.get("name", ""),
                "function_in_chapter": item.get("function_in_chapter", ""),
                "state_change": item.get("state_change", ""),
            }
            for item in script_data.get("character_usage") or []
            if item.get("name")
        }
        for scene in script_data.get("scenes") or []:
            for name in scene.get("characters") or []:
                usage.setdefault(
                    name,
                    {
                        "name": name,
                        "function_in_chapter": "出现在本幕场景中",
                        "state_change": "",
                    },
                )
        return list(usage.values())

    @staticmethod
    def _save_memory(
        *,
        request: ConvertProjectRequest,
        memory: dict[str, Any],
        rolling_summary: str,
        global_characters: list[dict[str, Any]],
        global_settings: list[dict[str, Any]],
        acts: list[dict[str, Any]],
    ) -> None:
        memory.setdefault("short_term", {})["window_chapters"] = request.short_term_window
        memory["book_title"] = memory.get("book_title") or ""
        memory["short_term"]["recent_chapters"] = [
            {
                "chapter_id": item["act_id"],
                "title": item["chapter_title"],
                "summary": item.get("chapter_summary") or f"{item['scene_count']} 场戏",
                "scene_ids": [],
                "active_characters": [
                    character["name"]
                    for character in item.get("character_introductions", [])
                    if character.get("name")
                ],
            }
            for item in acts[-request.short_term_window :]
        ]
        long_term = memory.setdefault("long_term", {})
        long_term["book_title"] = memory.get("book_title") or ""
        long_term["logline"] = rolling_summary[:500]
        long_term["characters"] = {
            f"char_{index:04d}": item for index, item in enumerate(global_characters, start=1)
        }
        long_term["locations"] = {
            f"setting_{index:04d}": item for index, item in enumerate(global_settings, start=1)
        }
        long_term["canon_facts"] = _dedupe_text_records(
            [
                *long_term.get("canon_facts", []),
                *[
                    fact.get("fact", "")
                    for act in acts
                    for fact in act.get("canon_facts", [])
                    if isinstance(fact, dict) and fact.get("fact")
                ],
            ],
            limit=120,
        )
        long_term["unresolved_threads"] = _dedupe_thread_records(
            [
                *long_term.get("unresolved_threads", []),
                *[
                    {"description": thread, "status": "open"}
                    for act in acts
                    for thread in act.get("open_threads", [])
                    if thread
                ],
            ],
            limit=120,
        )
        memory_store.save(request.user_id, request.thread_id, memory)


def _dedupe_text_records(items: list[Any], *, limit: int) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        text = item.get("fact", "") if isinstance(item, dict) else str(item or "")
        text = text.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output[-limit:]


def _dedupe_thread_records(items: list[Any], *, limit: int) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            description = str(item.get("description", "")).strip()
            status = str(item.get("status", "open")).strip() or "open"
        else:
            description = str(item or "").strip()
            status = "open"
        if not description or description in seen:
            continue
        seen.add(description)
        output.append({"description": description, "status": status})
    return output[-limit:]


script_project_service = ScriptProjectService()
