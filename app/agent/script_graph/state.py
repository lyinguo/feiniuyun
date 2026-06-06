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
    user_id: str
    book_title: str
    current_script_data: dict[str, Any]
    current_template_data: dict[str, Any]
    archivist_notes: dict[str, Any]
    background_notes: dict[str, Any]
    character_notes: dict[str, Any]
    relationship_notes: dict[str, Any]
    casting_notes: dict[str, Any]
    retrieved_memories: list[dict[str, Any]]
    previous_chapter_summaries: list[dict[str, Any]]
    template_schema: str
    critic_warnings: list[str]
    continuity_warnings: list[str]
    continuity_review: dict[str, Any]
    vector_memory_writes: int
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
    user_id: str = "",
    book_title: str = "",
    retrieved_memories: list[dict[str, Any]] | None = None,
    previous_chapter_summaries: list[dict[str, Any]] | None = None,
    template_schema: str = "",
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
        "user_id": user_id,
        "book_title": book_title,
        "current_script_data": {},
        "current_template_data": {},
        "archivist_notes": {},
        "background_notes": {},
        "character_notes": {},
        "relationship_notes": {},
        "casting_notes": {},
        "retrieved_memories": retrieved_memories or [],
        "previous_chapter_summaries": previous_chapter_summaries or [],
        "template_schema": template_schema,
        "critic_warnings": [],
        "continuity_warnings": [],
        "continuity_review": {},
        "vector_memory_writes": 0,
        "max_retries": max_retries,
        "scene_density": scene_density,
    }
