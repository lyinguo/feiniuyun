"""Node implementations for the multi-agent screenplay LangGraph workflow."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from app.agent.script_graph.llm import create_structured_llm
from app.agent.script_graph.memory_ops import compact_for_prompt, merge_archivist_output
from app.agent.script_graph.prompts import (
    ARCHIVIST_PROMPT,
    BACKGROUND_PROMPT,
    CASTING_PROMPT,
    CHARACTER_PROMPT,
    CRITIC_PROMPT,
    RELATIONSHIP_PROMPT,
    SCREENWRITER_PROMPT,
    SUMMARIZER_PROMPT,
    dump_prompt_json,
)
from app.agent.script_graph.schemas import (
    ArchivistOutput,
    BackgroundOutput,
    CastingOutput,
    CharacterOutput,
    ChapterScriptOutput,
    CriticOutput,
    GlobalCharacterProfile,
    RelationshipOutput,
    RelationshipProfile,
    RollingSummaryOutput,
)
from app.agent.script_graph.state import ScriptGraphState
from app.services.yaml_builder import to_yaml

logger = logging.getLogger(__name__)


async def background_node(state: ScriptGraphState) -> dict[str, Any]:
    """Extract screen-facing background, setting, and atmosphere notes."""

    logger.info("[Background] start chapter=%s", state.get("chapter_title") or state.get("chapter_index"))
    chain = BACKGROUND_PROMPT | create_structured_llm(BackgroundOutput, temperature=0.1)
    output: BackgroundOutput = await chain.ainvoke(
        {
            "chapter_title": state.get("chapter_title", ""),
            "current_chapter": state["current_chapter"],
            "rolling_summary": state.get("rolling_summary", ""),
            "global_settings": dump_prompt_json(compact_for_prompt(state.get("global_settings", []))),
        }
    )
    logger.info(
        "[Background] done settings=%d facts=%d",
        len(output.new_settings) + len(output.updated_settings),
        len(output.canon_facts),
    )
    return {"background_notes": output.model_dump()}


async def character_node(state: ScriptGraphState) -> dict[str, Any]:
    """Extract character archive updates before screenplay generation."""

    logger.info("[Character] start chapter=%s", state.get("chapter_title") or state.get("chapter_index"))
    chain = CHARACTER_PROMPT | create_structured_llm(CharacterOutput, temperature=0.1)
    output: CharacterOutput = await chain.ainvoke(
        {
            "chapter_title": state.get("chapter_title", ""),
            "current_chapter": state["current_chapter"],
            "rolling_summary": state.get("rolling_summary", ""),
            "global_characters": dump_prompt_json(
                compact_for_prompt(state.get("global_characters", []))
            ),
        }
    )
    logger.info(
        "[Character] done characters=%d",
        len(output.new_characters) + len(output.updated_characters),
    )
    return {"character_notes": output.model_dump()}


async def relationship_node(state: ScriptGraphState) -> dict[str, Any]:
    """Extract relationship and conflict lines in parallel with other analysis."""

    logger.info("[Relationship] start chapter=%s", state.get("chapter_title") or state.get("chapter_index"))
    chain = RELATIONSHIP_PROMPT | create_structured_llm(RelationshipOutput, temperature=0.1)
    output: RelationshipOutput = await chain.ainvoke(
        {
            "chapter_title": state.get("chapter_title", ""),
            "current_chapter": state["current_chapter"],
            "rolling_summary": state.get("rolling_summary", ""),
            "global_characters": dump_prompt_json(
                compact_for_prompt(state.get("global_characters", []))
            ),
        }
    )
    logger.info("[Relationship] done relationships=%d", len(output.relationships))
    return {"relationship_notes": output.model_dump()}


async def casting_node(state: ScriptGraphState) -> dict[str, Any]:
    """Extract casting, styling, and playable trait notes."""

    logger.info("[Casting] start chapter=%s", state.get("chapter_title") or state.get("chapter_index"))
    chain = CASTING_PROMPT | create_structured_llm(CastingOutput, temperature=0.15)
    output: CastingOutput = await chain.ainvoke(
        {
            "chapter_title": state.get("chapter_title", ""),
            "current_chapter": state["current_chapter"],
            "rolling_summary": state.get("rolling_summary", ""),
            "global_characters": dump_prompt_json(
                compact_for_prompt(state.get("global_characters", []))
            ),
            "global_settings": dump_prompt_json(compact_for_prompt(state.get("global_settings", []))),
        }
    )
    logger.info("[Casting] done choices=%d", len(output.choices))
    return {"casting_notes": output.model_dump()}


async def merge_prelude_node(state: ScriptGraphState) -> dict[str, Any]:
    """Merge parallel pre-analysis into global archives for the screenwriter."""

    background = BackgroundOutput.model_validate(state.get("background_notes") or {})
    characters = CharacterOutput.model_validate(state.get("character_notes") or {})
    relationships = RelationshipOutput.model_validate(state.get("relationship_notes") or {})
    casting = CastingOutput.model_validate(state.get("casting_notes") or {})

    relationship_profiles = [
        GlobalCharacterProfile(
            name=item.source_name,
            relationships=[
                RelationshipProfile(
                    target_name=item.target_name,
                    relation=item.relation,
                    evidence=item.evidence,
                )
            ],
            first_seen_chapter=state.get("chapter_title", ""),
            continuity_notes=[f"关系线索：{item.relation}"],
        )
        for item in relationships.relationships
    ]

    casting_profiles = [
        GlobalCharacterProfile(
            name=item.character_name,
            appearance=item.appearance_anchor or item.screen_type,
            first_seen_chapter=state.get("chapter_title", ""),
            continuity_notes=[
                *item.performance_notes,
                *item.costume_or_makeup,
            ],
        )
        for item in casting.choices
    ]

    archivist_output = ArchivistOutput(
        new_characters=characters.new_characters,
        updated_characters=[
            *characters.updated_characters,
            *relationship_profiles,
            *casting_profiles,
        ],
        new_settings=background.new_settings,
        updated_settings=background.updated_settings,
        canon_facts=background.canon_facts,
        continuity_risks=[
            *background.continuity_risks,
            *characters.continuity_risks,
            *relationships.continuity_risks,
            *casting.continuity_risks,
        ],
    )
    merged_characters, merged_settings, notes = merge_archivist_output(
        global_characters=state.get("global_characters", []),
        global_settings=state.get("global_settings", []),
        archivist_output=archivist_output,
    )
    notes.update(
        {
            "background": background.model_dump(),
            "characters": characters.model_dump(),
            "relationships": relationships.model_dump(),
            "casting": casting.model_dump(),
        }
    )

    logger.info(
        "[PreludeMerge] done characters=%d settings=%d",
        len(merged_characters),
        len(merged_settings),
    )
    return {
        "global_characters": merged_characters,
        "global_settings": merged_settings,
        "archivist_notes": notes,
    }


async def archivist_node(state: ScriptGraphState) -> dict[str, Any]:
    """Extract and merge character/setting archives from the current chapter."""

    logger.info(
        "[Archivist] start chapter=%s retry=%s",
        state.get("chapter_title") or state.get("chapter_index"),
        state.get("retry_count", 0),
    )

    chain = ARCHIVIST_PROMPT | create_structured_llm(ArchivistOutput, temperature=0.1)
    output: ArchivistOutput = await chain.ainvoke(
        {
            "chapter_title": state.get("chapter_title", ""),
            "current_chapter": state["current_chapter"],
            "rolling_summary": state.get("rolling_summary", ""),
            "global_characters": dump_prompt_json(
                compact_for_prompt(state.get("global_characters", []))
            ),
            "global_settings": dump_prompt_json(compact_for_prompt(state.get("global_settings", []))),
        }
    )

    characters, settings, notes = merge_archivist_output(
        global_characters=state.get("global_characters", []),
        global_settings=state.get("global_settings", []),
        archivist_output=output,
    )
    notes["raw_archivist_output"] = output.model_dump()

    logger.info(
        "[Archivist] done characters=%d settings=%d facts=%d",
        len(characters),
        len(settings),
        len(output.canon_facts),
    )

    return {
        "global_characters": characters,
        "global_settings": settings,
        "archivist_notes": notes,
    }


async def screenwriter_node(state: ScriptGraphState) -> dict[str, Any]:
    """Generate a structured screenplay draft for the current chapter."""

    logger.info(
        "[Screenwriter] start chapter=%s retry=%s error=%s",
        state.get("chapter_title") or state.get("chapter_index"),
        state.get("retry_count", 0),
        bool(state.get("error_msg")),
    )

    chain = SCREENWRITER_PROMPT | create_structured_llm(ChapterScriptOutput, temperature=0.25)
    output: ChapterScriptOutput = await chain.ainvoke(
        {
            "chapter_index": state.get("chapter_index", 1),
            "chapter_title": state.get("chapter_title", ""),
            "scene_density": state.get("scene_density", 3),
            "current_chapter": state["current_chapter"],
            "rolling_summary": state.get("rolling_summary", ""),
            "global_characters": dump_prompt_json(
                compact_for_prompt(state.get("global_characters", []))
            ),
            "global_settings": dump_prompt_json(compact_for_prompt(state.get("global_settings", []))),
            "archivist_notes": dump_prompt_json(state.get("archivist_notes", {})),
            "error_msg": state.get("error_msg", ""),
        }
    )

    script_data = output.model_dump()
    script_yaml = to_yaml(script_data)

    logger.info(
        "[Screenwriter] done scenes=%d yaml_chars=%d",
        len(output.scenes),
        len(script_yaml),
    )

    return {
        "current_script_data": script_data,
        "current_script_yaml": script_yaml,
        "error_msg": "",
    }


async def critic_node(state: ScriptGraphState) -> dict[str, Any]:
    """Validate the generated screenplay and produce retry instructions."""

    logger.info(
        "[Critic] start chapter=%s retry=%s",
        state.get("chapter_title") or state.get("chapter_index"),
        state.get("retry_count", 0),
    )

    deterministic_report = _deterministic_script_check(state)
    chain = CRITIC_PROMPT | create_structured_llm(CriticOutput, temperature=0.0)
    output: CriticOutput = await chain.ainvoke(
        {
            "deterministic_report": dump_prompt_json(deterministic_report),
            "global_characters": dump_prompt_json(
                compact_for_prompt(state.get("global_characters", []))
            ),
            "global_settings": dump_prompt_json(compact_for_prompt(state.get("global_settings", []))),
            "current_script_data": dump_prompt_json(state.get("current_script_data", {})),
            "current_script_yaml": state.get("current_script_yaml", ""),
        }
    )

    hard_failed = not deterministic_report["passed"] or not output.passed
    retry_count = int(state.get("retry_count", 0))
    max_retries = int(state.get("max_retries", 2))

    if hard_failed:
        retry_count += 1
        reason = deterministic_report["error_msg"] or output.error_msg or "剧本未通过审查。"
        if retry_count >= max_retries:
            logger.warning("[Critic] failed but reached max_retries=%d: %s", max_retries, reason)
            return {
                "error_msg": reason,
                "retry_count": retry_count,
                "critic_warnings": [
                    *deterministic_report["warnings"],
                    *output.warnings,
                    "已达到最大重试次数，后续图条件边应强制进入总结或结束。",
                ],
            }

        logger.warning("[Critic] failed retry=%d reason=%s", retry_count, reason)
        return {
            "error_msg": reason,
            "retry_count": retry_count,
            "critic_warnings": [*deterministic_report["warnings"], *output.warnings],
        }

    logger.info("[Critic] passed warnings=%d", len(output.warnings))
    return {
        "error_msg": "",
        "critic_warnings": [*deterministic_report["warnings"], *output.warnings],
    }


async def summarizer_node(state: ScriptGraphState) -> dict[str, Any]:
    """Update rolling summary after a chapter has passed review."""

    logger.info(
        "[Summarizer] start chapter=%s",
        state.get("chapter_title") or state.get("chapter_index"),
    )

    chain = SUMMARIZER_PROMPT | create_structured_llm(RollingSummaryOutput, temperature=0.15)
    output: RollingSummaryOutput = await chain.ainvoke(
        {
            "rolling_summary": state.get("rolling_summary", ""),
            "chapter_title": state.get("chapter_title", ""),
            "current_script_data": dump_prompt_json(state.get("current_script_data", {})),
            "critic_warnings": dump_prompt_json(state.get("critic_warnings", [])),
        }
    )

    logger.info(
        "[Summarizer] done summary_chars=%d open_threads=%d",
        len(output.rolling_summary),
        len(output.open_threads),
    )

    return {
        "rolling_summary": output.rolling_summary,
        "archivist_notes": {
            **state.get("archivist_notes", {}),
            "latest_summary_metadata": output.model_dump(),
        },
    }


def _deterministic_script_check(state: ScriptGraphState) -> dict[str, Any]:
    """Programmatic guardrail before the LLM critic adds semantic warnings."""

    warnings: list[str] = []
    data = state.get("current_script_data") or {}

    if not data:
        return {
            "passed": False,
            "error_msg": "current_script_data 为空，编剧节点没有产出结构化剧本。",
            "warnings": warnings,
        }

    try:
        parsed = ChapterScriptOutput.model_validate(data)
    except ValidationError as exc:
        return {
            "passed": False,
            "error_msg": f"ChapterScriptOutput 校验失败: {exc.errors()}",
            "warnings": warnings,
        }

    if not state.get("current_script_yaml", "").strip():
        return {
            "passed": False,
            "error_msg": "current_script_yaml 为空。",
            "warnings": warnings,
        }

    for index, scene in enumerate(parsed.scenes, start=1):
        if not scene.characters:
            warnings.append(f"第 {index} 场缺少出场人物。")
        if not scene.dialogue:
            warnings.append(f"第 {index} 场没有对白，需确认是否符合改编目标。")
        if len("".join(scene.action)) < 12:
            warnings.append(f"第 {index} 场动作描述过短，可能不可拍摄。")

    return {
        "passed": True,
        "error_msg": "",
        "warnings": warnings,
    }
