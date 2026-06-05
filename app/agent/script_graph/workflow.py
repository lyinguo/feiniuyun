"""StateGraph wiring and chapter-loop runner for the screenplay workflow."""

from __future__ import annotations

import logging
from typing import Any, Iterable

from langgraph.graph import END, START, StateGraph

from app.agent.script_graph.nodes import (
    archivist_node,
    critic_node,
    screenwriter_node,
    summarizer_node,
)
from app.agent.script_graph.state import ScriptGraphState, initial_script_graph_state
from app.services.chapter_splitter import Chapter

logger = logging.getLogger(__name__)

ARCHIVIST = "archivist"
SCREENWRITER = "screenwriter"
CRITIC = "critic"
SUMMARIZER = "summarizer"
ROUTE_RETRY = "retry"
ROUTE_SUMMARIZE = "summarize"


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


def build_script_graph():
    """Build and compile the LangGraph workflow."""

    graph = StateGraph(ScriptGraphState)

    graph.add_node(ARCHIVIST, archivist_node)
    graph.add_node(SCREENWRITER, screenwriter_node)
    graph.add_node(CRITIC, critic_node)
    graph.add_node(SUMMARIZER, summarizer_node)

    graph.add_edge(START, ARCHIVIST)
    graph.add_edge(ARCHIVIST, SCREENWRITER)
    graph.add_edge(SCREENWRITER, CRITIC)
    graph.add_conditional_edges(
        CRITIC,
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
    scene_density: int = 3,
    max_retries: int = 2,
) -> ScriptGraphState:
    """Run the compiled graph for one chapter."""

    logger.info(
        "[Runner] chapter start index=%s title=%s",
        chapter.index,
        chapter.title,
    )
    app = build_script_graph()
    state = initial_script_graph_state(
        current_chapter=chapter.text,
        chapter_index=chapter.index,
        chapter_title=chapter.title,
        rolling_summary=rolling_summary,
        global_characters=global_characters,
        global_settings=global_settings,
        scene_density=scene_density,
        max_retries=max_retries,
    )
    result: ScriptGraphState = await app.ainvoke(state)
    logger.info(
        "[Runner] chapter done index=%s scenes=%s retry=%s",
        chapter.index,
        len((result.get("current_script_data") or {}).get("scenes", [])),
        result.get("retry_count", 0),
    )
    return result


async def run_chapters(
    chapters: Iterable[Chapter],
    *,
    initial_rolling_summary: str = "",
    initial_global_characters: list[dict[str, Any]] | None = None,
    initial_global_settings: list[dict[str, Any]] | None = None,
    scene_density: int = 3,
    max_retries: int = 2,
) -> dict[str, Any]:
    """Run chapters sequentially while carrying rolling memory forward."""

    rolling_summary = initial_rolling_summary
    global_characters = list(initial_global_characters or [])
    global_settings = list(initial_global_settings or [])
    chapter_results: list[dict[str, Any]] = []

    for chapter in chapters:
        result = await run_chapter(
            chapter,
            rolling_summary=rolling_summary,
            global_characters=global_characters,
            global_settings=global_settings,
            scene_density=scene_density,
            max_retries=max_retries,
        )
        rolling_summary = result.get("rolling_summary", rolling_summary)
        global_characters = result.get("global_characters", global_characters)
        global_settings = result.get("global_settings", global_settings)
        chapter_results.append(
            {
                "chapter_index": chapter.index,
                "chapter_title": chapter.title,
                "script_data": result.get("current_script_data", {}),
                "script_yaml": result.get("current_script_yaml", ""),
                "critic_warnings": result.get("critic_warnings", []),
                "error_msg": result.get("error_msg", ""),
                "retry_count": result.get("retry_count", 0),
            }
        )

    return {
        "rolling_summary": rolling_summary,
        "global_characters": global_characters,
        "global_settings": global_settings,
        "chapters": chapter_results,
    }

