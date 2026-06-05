"""LangGraph state definition for the screenplay workflow."""

from __future__ import annotations

from typing import Any, TypedDict


class ScriptGraphState(TypedDict):
    """Global state shared by all LangGraph nodes.

    Required fields follow the requested blueprint exactly. Additional fields
    are included for observability and safe orchestration, but node functions
    should treat this state as JSON-serializable data.
    """

    # Required by blueprint.
    current_chapter: str
    global_characters: list[dict[str, Any]]
    global_settings: list[dict[str, Any]]
    rolling_summary: str
    current_script_yaml: str
    error_msg: str
    retry_count: int

    # Useful orchestration metadata for later nodes and demos.
    chapter_index: int
    chapter_title: str
    current_script_data: dict[str, Any]
    archivist_notes: dict[str, Any]
    critic_warnings: list[str]
    max_retries: int
    scene_density: int


def initial_script_graph_state(
    *,
    current_chapter: str,
    chapter_index: int = 1,
    chapter_title: str = "",
    rolling_summary: str = "",
    global_characters: list[dict[str, Any]] | None = None,
    global_settings: list[dict[str, Any]] | None = None,
    max_retries: int = 2,
    scene_density: int = 3,
) -> ScriptGraphState:
    """Create a clean state object for one chapter run."""

    return {
        "current_chapter": current_chapter,
        "global_characters": global_characters or [],
        "global_settings": global_settings or [],
        "rolling_summary": rolling_summary,
        "current_script_yaml": "",
        "error_msg": "",
        "retry_count": 0,
        "chapter_index": chapter_index,
        "chapter_title": chapter_title,
        "current_script_data": {},
        "archivist_notes": {},
        "critic_warnings": [],
        "max_retries": max_retries,
        "scene_density": scene_density,
    }
