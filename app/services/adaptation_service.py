"""High-level novel-to-screenplay adaptation pipeline."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List

from app.config import settings
from app.core.llm_client import ChatMessage, OpenAICompatibleLLMClient, llm_client
from app.core.mcp_client import load_mcp_tool_metadata
from app.models.request import ConvertNovelRequest
from app.services.chapter_splitter import Chapter, chapter_splitter
from app.services.llm_output_parser import ensure_list, ensure_string
from app.services.memory_store import memory_store
from app.services.prompt_builder import build_chapter_messages
from app.services.schema_validator import screenplay_schema_validator
from app.services.story_registry import StoryRegistry
from app.services.yaml_builder import to_yaml
from app.tools import default_tool_registry


class AdaptationError(RuntimeError):
    """Raised for user-visible adaptation failures."""


class NovelAdaptationService:
    def __init__(self, model_client: OpenAICompatibleLLMClient | None = None):
        self.model_client = model_client or llm_client

    async def convert(self, request: ConvertNovelRequest) -> Dict[str, Any]:
        if len(request.novel_text) > settings.max_input_chars:
            raise AdaptationError(
                f"novel_text is too large for one request: {len(request.novel_text)} chars. "
                f"Current limit is {settings.max_input_chars}. Split the manuscript by volume or batch."
            )

        chapters = chapter_splitter.split(request.novel_text)
        diagnostics: list[str] = []

        if len(chapters) < 3:
            raise AdaptationError("至少需要 3 个章节以上的小说文本。")

        if any(chapter.auto_generated for chapter in chapters):
            diagnostics.append(
                "未识别到稳定章节标题，后端按长度自动分章；正式稿建议保留“第一章/第二章”标题。"
            )

        max_chapters = request.max_chapters or settings.max_chapters_per_request
        if len(chapters) > max_chapters:
            raise AdaptationError(
                f"当前请求识别到 {len(chapters)} 章，超过单次上限 {max_chapters}。"
                "请分批提交，或提高 MAX_CHAPTERS_PER_REQUEST。"
            )

        project = {
            "title": request.title or self._derive_title(request.novel_text, chapters),
            "source_type": "novel",
            "target_format": request.target_format,
            "adaptation_tone": request.adaptation_tone,
            "language": "zh-CN",
        }

        base_memory = memory_store.load(
            request.user_id,
            request.thread_id,
            request.short_term_window,
        )
        working_memory = deepcopy(base_memory)
        working_memory["short_term"]["window_chapters"] = request.short_term_window
        registry = StoryRegistry(working_memory)
        mcp_metadata = await load_mcp_tool_metadata()

        chapter_results: list[dict[str, Any]] = []
        for chapter in chapters:
            output = await self._generate_chapter(
                project=project,
                chapter=chapter,
                request=request,
                memory=working_memory,
                mcp_metadata=mcp_metadata,
            )
            registry.ingest_chapter_output(chapter.chapter_id, output)
            self._stamp_scene_source(output, chapter)
            scenes = registry.normalize_scenes(
                chapter.chapter_id,
                chapter.index,
                output,
            )

            chapter_summary = ensure_string(output.get("chapter_summary"), "待补充章节摘要")
            chapter_results.append(
                {
                    "chapter": chapter,
                    "summary": chapter_summary,
                    "raw_output": output,
                    "scenes": scenes,
                    "revision_notes": [
                        ensure_string(item)
                        for item in ensure_list(output.get("chapter_revision_notes"))
                        if ensure_string(item)
                    ],
                }
            )
            self._update_short_term(
                working_memory,
                chapter,
                chapter_summary,
                scenes,
                request.short_term_window,
            )

        self._update_logline(working_memory, project["title"], chapter_results)
        script = self._build_script(
            request=request,
            project=project,
            chapters=chapters,
            chapter_results=chapter_results,
            memory=working_memory,
            registry=registry,
            diagnostics=diagnostics,
            mcp_metadata=mcp_metadata,
        )

        report = screenplay_schema_validator.validate(script)
        if not report.valid:
            raise AdaptationError("生成结果未通过 YAML Schema 校验: " + "; ".join(report.errors))

        script["review_notes"]["warnings"].extend(report.warnings)
        yaml_text = to_yaml(script)
        memory_store.save(request.user_id, request.thread_id, working_memory)

        return {
            "user_id": request.user_id,
            "thread_id": request.thread_id,
            "yaml": yaml_text,
            "script": script,
            "diagnostics": script["review_notes"]["warnings"],
            "stats": {
                "chapter_count": len(chapters),
                "scene_count": sum(len(item["scenes"]) for item in chapter_results),
                "character_count": len(script["characters"]),
                "location_count": len(script["locations"]),
                "model_call_count": len(chapters),
                "source_char_count": len(request.novel_text),
            },
            "memory_snapshot": working_memory,
        }

    async def _generate_chapter(
        self,
        *,
        project: Dict[str, Any],
        chapter: Chapter,
        request: ConvertNovelRequest,
        memory: Dict[str, Any],
        mcp_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        short_term = memory.get("short_term", {}).get("recent_chapters", [])[
            -request.short_term_window :
        ]
        long_term = memory.get("long_term", {})
        tool_context = default_tool_registry.build_context(chapter.text)
        tool_context["mcp_tools"] = mcp_metadata

        messages = [
            ChatMessage(role=item["role"], content=item["content"])
            for item in build_chapter_messages(
                project=project,
                chapter=chapter,
                scene_density=request.scene_density,
                short_term_memory=short_term,
                long_term_memory=long_term,
                tool_context=tool_context,
            )
        ]
        output = await self.model_client.chat_json(messages)
        if not isinstance(output, dict):
            raise AdaptationError(f"{chapter.title} 模型输出不是 JSON object。")
        output.setdefault("chapter_summary", "")
        output.setdefault("characters", [])
        output.setdefault("locations", [])
        output.setdefault("canon_facts", [])
        output.setdefault("unresolved_threads", [])
        output.setdefault("scenes", [])
        return output

    def _build_script(
        self,
        *,
        request: ConvertNovelRequest,
        project: Dict[str, Any],
        chapters: List[Chapter],
        chapter_results: List[Dict[str, Any]],
        memory: Dict[str, Any],
        registry: StoryRegistry,
        diagnostics: List[str],
        mcp_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        episodes = []
        for offset in range(0, len(chapter_results), request.chapters_per_episode):
            group = chapter_results[offset : offset + request.chapters_per_episode]
            episode_index = len(episodes) + 1
            episodes.append(
                {
                    "episode_id": f"ep_{episode_index:03d}",
                    "title": f"第{episode_index}集：{group[0]['chapter'].title}",
                    "source_chapters": [item["chapter"].index for item in group],
                    "dramatic_goal": self._episode_goal(group),
                    "acts": [
                        {
                            "act_id": f"ep_{episode_index:03d}_act_{act_index + 1:03d}",
                            "title": item["chapter"].title,
                            "source_chapter": item["chapter"].index,
                            "dramatic_function": self._act_function(act_index, len(group)),
                            "chapter_summary": item["summary"],
                            "carried_memory": {
                                "recent_chapters": [
                                    recent.get("chapter_id")
                                    for recent in memory.get("short_term", {}).get(
                                        "recent_chapters", []
                                    )
                                ],
                                "open_threads": [
                                    thread.get("thread_id")
                                    for thread in memory.get("long_term", {}).get(
                                        "unresolved_threads", []
                                    )[-12:]
                                ],
                            },
                            "scenes": item["scenes"],
                        }
                        for act_index, item in enumerate(group)
                    ],
                }
            )

        return {
            "schema_version": "1.0",
            "project": project,
            "source": {
                "chapter_count": len(chapters),
                "character_count": sum(len(chapter.text) for chapter in chapters),
                "detected_chaptering": (
                    "auto_by_length"
                    if any(chapter.auto_generated for chapter in chapters)
                    else "heading"
                ),
                "minimum_requirement_met": len(chapters) >= 3,
            },
            "memory": {
                "short_term": memory.get("short_term", {}),
                "long_term": memory.get("long_term", {}),
            },
            "characters": registry.characters_list(),
            "locations": registry.locations_list(),
            "script": {
                "format": "episode_act_scene",
                "episodes": episodes,
            },
            "tooling": {
                "local_tools": ["screenplay_yaml_schema", "chapter_text_stats"],
                "mcp": mcp_metadata,
            },
            "review_notes": {
                "warnings": diagnostics,
                "next_revision": self._collect_revision_notes(chapter_results),
            },
        }

    @staticmethod
    def _stamp_scene_source(output: Dict[str, Any], chapter: Chapter) -> None:
        for scene in ensure_list(output.get("scenes")):
            if isinstance(scene, dict):
                scene.setdefault("source_chapter_title", chapter.title)

    @staticmethod
    def _update_short_term(
        memory: Dict[str, Any],
        chapter: Chapter,
        summary: str,
        scenes: List[Dict[str, Any]],
        window: int,
    ) -> None:
        short_term = memory.setdefault("short_term", {})
        short_term["window_chapters"] = window
        recent = short_term.setdefault("recent_chapters", [])
        recent.append(
            {
                "chapter_id": chapter.chapter_id,
                "title": chapter.title,
                "summary": summary,
                "scene_ids": [scene["scene_id"] for scene in scenes],
                "active_characters": sorted(
                    {
                        character_id
                        for scene in scenes
                        for character_id in scene.get("characters", [])
                    }
                ),
            }
        )
        short_term["recent_chapters"] = recent[-window:]

    @staticmethod
    def _update_logline(
        memory: Dict[str, Any],
        title: str,
        chapter_results: List[Dict[str, Any]],
    ) -> None:
        if not chapter_results:
            return
        first = chapter_results[0]["summary"]
        last = chapter_results[-1]["summary"]
        memory.setdefault("long_term", {})["logline"] = f"{title}：{first} {last}"[:240]

    @staticmethod
    def _derive_title(text: str, chapters: List[Chapter]) -> str:
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        if first_line and len(first_line) <= 40 and not first_line.startswith("第"):
            return first_line.strip("《》")
        return chapters[0].title if chapters else "未命名改编项目"

    @staticmethod
    def _episode_goal(group: List[Dict[str, Any]]) -> str:
        if not group:
            return "待确认"
        return f"{group[0]['summary']} -> {group[-1]['summary']}"[:180]

    @staticmethod
    def _act_function(index: int, total: int) -> str:
        if index == 0:
            return "建立人物、目标与当前处境"
        if index == total - 1:
            return "形成阶段性转折或悬念"
        return "推进调查、关系或外部阻碍"

    @staticmethod
    def _collect_revision_notes(chapter_results: List[Dict[str, Any]]) -> List[str]:
        notes = [
            "人工确认人物名、地点名和章节来源，修正模型误识别。",
            "检查每场戏是否只有一个明确戏剧目的。",
            "把保留的心理描写继续改成可拍摄动作或对白。",
        ]
        for item in chapter_results:
            notes.extend(item.get("revision_notes", []))
        deduped: list[str] = []
        for note in notes:
            if note and note not in deduped:
                deduped.append(note)
        return deduped[:30]


novel_adaptation_service = NovelAdaptationService()
