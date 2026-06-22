"""StateGraph wiring and chapter-loop runner for the screenplay workflow."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable

from langgraph.graph import END, START, StateGraph

from app.agent.script_graph.nodes import (
    background_node,
    casting_node,
    character_node,
    continuity_critic_node,
    critic_node,
    merge_prelude_node,
    relationship_node,
    screenwriter_node,
    summarizer_node,
)
from app.agent.script_graph.state import ScriptGraphState, initial_script_graph_state
from app.agent.script_graph.memory_ops import compact_text_for_prompt
from app.services.chapter_splitter import Chapter
from app.services.vector_memory import vector_story_memory

logger = logging.getLogger(__name__)

BACKGROUND = "background"
CHARACTER = "character"
RELATIONSHIP = "relationship"
CASTING = "casting"
PRELUDE_MERGE = "prelude_merge"
SCREENWRITER = "screenwriter"
CRITIC = "critic"
CONTINUITY_CRITIC = "continuity_critic"
SUMMARIZER = "summarizer"
ROUTE_RETRY = "retry"
ROUTE_CONTINUITY = "continuity"
ROUTE_SUMMARIZE = "summarize"

TEMPLATE_PATH = Path(__file__).resolve().parents[3] / "template.yaml"
DIRECT_SUMMARY_CHAR_LIMIT = 1800
RAG_RESULT_LIMIT = 6
PREVIOUS_SUMMARY_DIRECT_LIMIT = 1


def route_after_critic(state: ScriptGraphState) -> str:
    """Conditional edge after Critic.

    Failed validation returns to Screenwriter until max_retries is reached.
    Once retry budget is exhausted, the graph moves forward so the workflow
    cannot loop forever.
    """

    error_msg = (state.get("error_msg") or "").strip()
    retry_count = int(state.get("retry_count", 0))
    max_retries = int(state.get("max_retries", 2))

    if error_msg and retry_count < max_retries:
        logger.info(
            "[Graph] route critic -> screenwriter retry=%d/%d",
            retry_count,
            max_retries,
        )
        return ROUTE_RETRY

    logger.info(
        "[Graph] route critic -> summarizer retry=%d/%d error=%s",
        retry_count,
        max_retries,
        bool(error_msg),
    )
    return ROUTE_SUMMARIZE


def route_after_format_critic(state: ScriptGraphState) -> str:
    """Route after schema/format critic.

    Clean format continues to the final continuity judge. Failed format retries
    while retry budget remains; exhausted failures skip the continuity judge so
    an invalid draft is not judged semantically.
    """

    error_msg = (state.get("error_msg") or "").strip()
    retry_count = int(state.get("retry_count", 0))
    max_retries = int(state.get("max_retries", 2))

    if error_msg and retry_count < max_retries:
        logger.info(
            "[Graph] route format critic -> screenwriter retry=%d/%d",
            retry_count,
            max_retries,
        )
        return ROUTE_RETRY
    if error_msg:
        logger.info(
            "[Graph] route format critic -> summarizer exhausted retry=%d/%d",
            retry_count,
            max_retries,
        )
        return ROUTE_SUMMARIZE
    logger.info("[Graph] route format critic -> continuity judge")
    return ROUTE_CONTINUITY


def build_script_graph():
    """Build and compile the LangGraph workflow.

    The graph first fans out into lightweight analysis agents. Their outputs
    are merged into the story archive, then the screenwriter drafts the chapter.
    """

    graph = StateGraph(ScriptGraphState)

    graph.add_node(BACKGROUND, background_node)
    graph.add_node(CHARACTER, character_node)
    graph.add_node(RELATIONSHIP, relationship_node)
    graph.add_node(CASTING, casting_node)
    graph.add_node(PRELUDE_MERGE, merge_prelude_node)
    graph.add_node(SCREENWRITER, screenwriter_node)
    graph.add_node(CRITIC, critic_node)
    graph.add_node(CONTINUITY_CRITIC, continuity_critic_node)
    graph.add_node(SUMMARIZER, summarizer_node)

    graph.add_edge(START, BACKGROUND)
    graph.add_edge(START, CHARACTER)
    graph.add_edge(START, RELATIONSHIP)
    graph.add_edge(START, CASTING)
    graph.add_edge(BACKGROUND, PRELUDE_MERGE)
    graph.add_edge(CHARACTER, PRELUDE_MERGE)
    graph.add_edge(RELATIONSHIP, PRELUDE_MERGE)
    graph.add_edge(CASTING, PRELUDE_MERGE)
    graph.add_edge(PRELUDE_MERGE, SCREENWRITER)
    graph.add_edge(SCREENWRITER, CRITIC)
    graph.add_conditional_edges(
        CRITIC,
        route_after_format_critic,
        {
            ROUTE_RETRY: SCREENWRITER,
            ROUTE_CONTINUITY: CONTINUITY_CRITIC,
            ROUTE_SUMMARIZE: SUMMARIZER,
        },
    )
    graph.add_conditional_edges(
        CONTINUITY_CRITIC,
        route_after_critic,
        {
            ROUTE_RETRY: SCREENWRITER,
            ROUTE_SUMMARIZE: SUMMARIZER,
        },
    )
    graph.add_edge(SUMMARIZER, END)

    return graph.compile()


async def run_chapter(
    chapter: Chapter,
    *,
    rolling_summary: str = "",
    global_characters: list[dict[str, Any]] | None = None,
    global_settings: list[dict[str, Any]] | None = None,
    user_id: str = "",
    book_title: str = "",
    retrieved_memories: list[dict[str, Any]] | None = None,
    previous_chapter_summaries: list[dict[str, Any]] | None = None,
    template_schema: str | None = None,
    scene_density: int = 3,
    max_retries: int = 2,
    send_event_callback=None,
) -> ScriptGraphState:
    """Run the compiled graph for one chapter."""

    logger.info(
        "[Runner] chapter start index=%s title=%s",
        chapter.index,
        chapter.title,
    )
    app = build_script_graph()
    effective_template_schema = template_schema if template_schema is not None else load_template_schema()
    effective_retrieved_memories = retrieved_memories
    if effective_retrieved_memories is None and user_id and book_title:
        effective_retrieved_memories = vector_story_memory.search(
            user_id=user_id,
            book_title=book_title,
            query=_memory_query(chapter, rolling_summary),
            limit=RAG_RESULT_LIMIT,
        )
    state = initial_script_graph_state(
        current_chapter=chapter.text,
        chapter_index=chapter.index,
        chapter_title=chapter.title,
        rolling_summary=compact_text_for_prompt(rolling_summary, DIRECT_SUMMARY_CHAR_LIMIT),
        global_characters=global_characters,
        global_settings=global_settings,
        user_id=user_id,
        book_title=book_title,
        retrieved_memories=effective_retrieved_memories,
        previous_chapter_summaries=_recent_previous_summaries(previous_chapter_summaries),
        template_schema=effective_template_schema,
        scene_density=scene_density,
        max_retries=max_retries,
    )

    # 🟢 替换为流式新代码：
    final_state = None
    allowed_agents = [
        "background", "character", "relationship", "casting", 
        "screenwriter", 
        "critic", "continuity_critic", "summarizer" # 👈 新增这三个
    ]
    async for event in app.astream_events(state, version="v2"):
        # print("进入判断")
        kind = event["event"]
        node_name = event.get("metadata", {}).get("langgraph_node", "unknown")
        if kind == "on_chain_start" and node_name in allowed_agents:
            # print("进入判断1")
            if send_event_callback:
                send_event_callback({"type": "agent_start", "agent": node_name})

        # 拦截 2：大模型正在流式输出
        elif kind == "on_chat_model_stream":
            # print("进入判断2")
            chunk = event["data"]["chunk"]
            
            # 1. 拦截所有模型的深度思考 (Reasoning)
            reasoning = getattr(chunk, "reasoning_content", None) or getattr(chunk.message, "reasoning_content", None) if hasattr(chunk, "message") else None
            # print(reasoning, end="", flush=True) 
            if reasoning and send_event_callback:
                
                send_event_callback({
                    "type": "reasoning",
                    "agent": node_name,  # 可能是 background, character, screenwriter 等任何一个
                    "content": reasoning
                })
                
            # 2. 拦截正文输出 (Token)
            content = chunk.content
            if not content and hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
                content = chunk.tool_call_chunks[0].get("args", "")
            # print(content, end="", flush=True) 
            if content and send_event_callback:
                # 如果你依然觉得前端展示 JSON 碎片太丑，就只保留 screenwriter。
                if node_name in allowed_agents:
                    
                    send_event_callback({
                        "type": "token",
                        "agent": node_name,
                        "content": content
                    })

        # elif kind == "on_chain_end" and not event.get("name"):
        elif kind == "on_chain_end" :
            event_name = event.get("name")
            if event_name == "LangGraph":
                print("翻页")
                final_state = event["data"]["output"]
                if send_event_callback:
                    send_event_callback({
                        "type": "chapter_done", # 专门定义一个新类型：章节完成
                        "unit_index": chapter.index-1 # 告诉前端是哪一章完成了
                    })
            # final_state = event["data"]["output"]
            elif event_name in allowed_agents:
                if send_event_callback:
                    send_event_callback({
                        "type": "agent_done", # 👈 发送完成信号！
                        "agent": node_name
                    })

    # 🌟 关键桥梁：把流式跑完的最终状态，无缝无感地还给原有的 result 变量
    result: ScriptGraphState = final_state

    if user_id and book_title:
        docs_written = vector_story_memory.add_graph_extracts(
            user_id=user_id,
            book_title=book_title,
            chapter_title=chapter.title,
            archivist_notes=result.get("archivist_notes", {}),
            summary_metadata=(result.get("archivist_notes", {}) or {}).get(
                "latest_summary_metadata",
                {},
            ),
        )
        result["vector_memory_writes"] = docs_written
    logger.info(
        "[Runner] chapter done index=%s scenes=%s retry=%s memories=%s",
        chapter.index,
        len((result.get("current_script_data") or {}).get("scenes", [])),
        result.get("retry_count", 0),
        len(result.get("retrieved_memories") or []),
    )
    return result


async def run_chapters(
    chapters: Iterable[Chapter],
    *,
    initial_rolling_summary: str = "",
    initial_global_characters: list[dict[str, Any]] | None = None,
    initial_global_settings: list[dict[str, Any]] | None = None,
    user_id: str = "",
    book_title: str = "",
    template_schema: str | None = None,
    scene_density: int = 3,
    max_retries: int = 2,
) -> dict[str, Any]:
    """Run chapters sequentially while carrying rolling memory forward."""

    rolling_summary = initial_rolling_summary
    global_characters = list(initial_global_characters or [])
    global_settings = list(initial_global_settings or [])
    chapter_results: list[dict[str, Any]] = []
    previous_chapter_summaries: list[dict[str, Any]] = []
    effective_template_schema = template_schema if template_schema is not None else load_template_schema()

    for chapter in chapters:
        result = await run_chapter(
            chapter,
            rolling_summary=rolling_summary,
            global_characters=global_characters,
            global_settings=global_settings,
            user_id=user_id,
            book_title=book_title,
            previous_chapter_summaries=previous_chapter_summaries,
            template_schema=effective_template_schema,
            scene_density=scene_density,
            max_retries=max_retries,
        )
        rolling_summary = compact_text_for_prompt(
            result.get("rolling_summary", rolling_summary),
            DIRECT_SUMMARY_CHAR_LIMIT,
        )
        global_characters = result.get("global_characters", global_characters)
        global_settings = result.get("global_settings", global_settings)
        chapter_results.append(
            {
                "chapter_index": chapter.index,
                "chapter_title": chapter.title,
                "script_data": result.get("current_script_data", {}),
                "template_data": result.get("current_template_data", {}),
                "script_yaml": result.get("current_script_yaml", ""),
                "critic_warnings": result.get("critic_warnings", []),
                "continuity_review": result.get("continuity_review", {}),
                "error_msg": result.get("error_msg", ""),
                "retry_count": result.get("retry_count", 0),
            }
        )
        script_data = result.get("current_script_data") or {}
        previous_chapter_summaries.append(
            {
                "chapter_index": chapter.index,
                "chapter_title": chapter.title,
                "summary": script_data.get("chapter_summary", ""),
                "rolling_summary_after": rolling_summary,
            }
        )

    return {
        "rolling_summary": rolling_summary,
        "global_characters": global_characters,
        "global_settings": global_settings,
        "chapters": chapter_results,
    }


def load_template_schema() -> str:
    """Load the user-provided per-chapter YAML template."""

    try:
        return TEMPLATE_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        logger.warning("template.yaml not found at %s", TEMPLATE_PATH)
        return ""


def _recent_previous_summaries(items: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return list(items or [])[-PREVIOUS_SUMMARY_DIRECT_LIMIT:]


def _memory_query(chapter: Chapter, rolling_summary: str) -> str:
    source = chapter.text.strip()
    return "\n".join(
        item
        for item in [
            chapter.title,
            compact_text_for_prompt(rolling_summary, 1000),
            source[:2500],
        ]
        if item
    )
