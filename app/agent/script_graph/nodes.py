"""Node implementations for the multi-agent screenplay LangGraph workflow."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from app.agent.script_graph.llm import GraphLLMResponseError, invoke_structured
from app.agent.script_graph.memory_ops import (
    compact_for_prompt,
    compact_text_for_prompt,
    merge_archivist_output,
)
from app.agent.script_graph.prompts import (
    ARCHIVIST_PROMPT,
    BACKGROUND_PROMPT,
    CASTING_PROMPT,
    CHARACTER_PROMPT,
    CONTINUITY_CRITIC_PROMPT,
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
    ContinuityReviewOutput,
    CriticOutput,
    DialogueLine,
    SceneContinuity,
    ScreenwriterDraftOutput,
    ScriptScene,
    Slugline,
    SourceReference,
    CharacterUsage,
    GlobalCharacterProfile,
    RelationshipOutput,
    RelationshipProfile,
    RollingSummaryOutput,
    SettingUsage,
)
from app.agent.script_graph.state import ScriptGraphState
from app.services.yaml_builder import to_yaml

logger = logging.getLogger(__name__)

CHARACTER_PROMPT_ARCHIVE_LIMIT = 16
SETTING_PROMPT_ARCHIVE_LIMIT = 12
RETRIEVED_MEMORY_PROMPT_LIMIT = 6
PREVIOUS_SUMMARY_PROMPT_LIMIT = 1
ROLLING_SUMMARY_PROMPT_CHARS = 1200
COMPACT_RETRY_CHAPTER_CHARS = 5000


def _prompt_rolling_summary(state: ScriptGraphState) -> str:
    return compact_text_for_prompt(
        state.get("rolling_summary", ""),
        ROLLING_SUMMARY_PROMPT_CHARS,
    )


def _prompt_global_characters(state: ScriptGraphState, limit: int = CHARACTER_PROMPT_ARCHIVE_LIMIT) -> str:
    return dump_prompt_json(compact_for_prompt(state.get("global_characters", []), limit=limit))


def _prompt_global_settings(state: ScriptGraphState, limit: int = SETTING_PROMPT_ARCHIVE_LIMIT) -> str:
    return dump_prompt_json(compact_for_prompt(state.get("global_settings", []), limit=limit))


def _prompt_previous_summaries(state: ScriptGraphState, limit: int = PREVIOUS_SUMMARY_PROMPT_LIMIT) -> str:
    return dump_prompt_json(compact_for_prompt(state.get("previous_chapter_summaries", []), limit=limit))


def _prompt_retrieved_memories(state: ScriptGraphState, limit: int = RETRIEVED_MEMORY_PROMPT_LIMIT) -> str:
    return dump_prompt_json(compact_for_prompt(state.get("retrieved_memories", []), limit=limit))


async def background_node(state: ScriptGraphState) -> dict[str, Any]:
    """Extract screen-facing background, setting, and atmosphere notes."""

    logger.info("[Background] start chapter=%s", state.get("chapter_title") or state.get("chapter_index"))
    try:
        output = await invoke_structured(
            BACKGROUND_PROMPT,
            BackgroundOutput,
            {
                "chapter_title": state.get("chapter_title", ""),
                "current_chapter": state["current_chapter"],
                "rolling_summary": _prompt_rolling_summary(state),
                "global_settings": _prompt_global_settings(state),
            },
            temperature=0.1,
        )
    except GraphLLMResponseError as exc:
        logger.warning(
            "[Background] skipped chapter=%s error=%s",
            state.get("chapter_title") or state.get("chapter_index"),
            exc,
        )
        output = BackgroundOutput(
            continuity_risks=[
                "Background extraction failed for this chapter; skipped archive update.",
            ]
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
    try:
        output = await _invoke_character_extractor(
            state,
            current_chapter=state["current_chapter"],
            archive_limit=CHARACTER_PROMPT_ARCHIVE_LIMIT,
        )
    except GraphLLMResponseError as exc:
        logger.warning(
            "[Character] failed, retrying with compact context chapter=%s error=%s",
            state.get("chapter_title") or state.get("chapter_index"),
            exc,
        )
        try:
            output = await _invoke_character_extractor(
                state,
                current_chapter=compact_text_for_prompt(
                    state["current_chapter"],
                    COMPACT_RETRY_CHAPTER_CHARS,
                ),
                archive_limit=8,
            )
        except GraphLLMResponseError as retry_exc:
            logger.warning(
                "[Character] skipped after compact retry chapter=%s error=%s",
                state.get("chapter_title") or state.get("chapter_index"),
                retry_exc,
            )
            output = CharacterOutput(
                continuity_risks=[
                    "Character extraction failed for this chapter; skipped archive update.",
                ]
            )
    logger.info(
        "[Character] done characters=%d",
        len(output.new_characters) + len(output.updated_characters),
    )
    return {"character_notes": output.model_dump()}


async def _invoke_character_extractor(
    state: ScriptGraphState,
    *,
    current_chapter: str,
    archive_limit: int,
) -> CharacterOutput:
    return await invoke_structured(
        CHARACTER_PROMPT,
        CharacterOutput,
        {
            "chapter_title": state.get("chapter_title", ""),
            "current_chapter": current_chapter,
            "rolling_summary": _prompt_rolling_summary(state),
            "global_characters": _prompt_global_characters(state, limit=archive_limit),
        },
        temperature=0.1,
    )


async def relationship_node(state: ScriptGraphState) -> dict[str, Any]:
    """Extract relationship and conflict lines in parallel with other analysis."""

    logger.info("[Relationship] start chapter=%s", state.get("chapter_title") or state.get("chapter_index"))
    try:
        output = await invoke_structured(
            RELATIONSHIP_PROMPT,
            RelationshipOutput,
            {
                "chapter_title": state.get("chapter_title", ""),
                "current_chapter": state["current_chapter"],
                "rolling_summary": _prompt_rolling_summary(state),
                "global_characters": _prompt_global_characters(state),
            },
            temperature=0.1,
        )
    except GraphLLMResponseError as exc:
        logger.warning(
            "[Relationship] skipped chapter=%s error=%s",
            state.get("chapter_title") or state.get("chapter_index"),
            exc,
        )
        output = RelationshipOutput(
            continuity_risks=[
                "Relationship extraction failed for this chapter; skipped relationship update.",
            ]
        )
    logger.info("[Relationship] done relationships=%d", len(output.relationships))
    return {"relationship_notes": output.model_dump()}


async def casting_node(state: ScriptGraphState) -> dict[str, Any]:
    """Extract casting, styling, and playable trait notes."""

    logger.info("[Casting] start chapter=%s", state.get("chapter_title") or state.get("chapter_index"))
    try:
        output = await invoke_structured(
            CASTING_PROMPT,
            CastingOutput,
            {
                "chapter_title": state.get("chapter_title", ""),
                "current_chapter": state["current_chapter"],
                "rolling_summary": _prompt_rolling_summary(state),
                "global_characters": _prompt_global_characters(state),
                "global_settings": _prompt_global_settings(state),
            },
            temperature=0.15,
        )
    except GraphLLMResponseError as exc:
        logger.warning(
            "[Casting] skipped chapter=%s error=%s",
            state.get("chapter_title") or state.get("chapter_index"),
            exc,
        )
        output = CastingOutput(
            continuity_risks=[
                "Casting extraction failed for this chapter; skipped casting update.",
            ]
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

    output = await invoke_structured(
        ARCHIVIST_PROMPT,
        ArchivistOutput,
        {
            "chapter_title": state.get("chapter_title", ""),
            "current_chapter": state["current_chapter"],
            "rolling_summary": _prompt_rolling_summary(state),
            "global_characters": _prompt_global_characters(state),
            "global_settings": _prompt_global_settings(state),
        },
        temperature=0.1,
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

    output = await invoke_structured(
        SCREENWRITER_PROMPT,
        ScreenwriterDraftOutput,
        {
            "chapter_index": state.get("chapter_index", 1),
            "chapter_title": state.get("chapter_title", ""),
            "scene_density": state.get("scene_density", 3),
            "current_chapter": state["current_chapter"],
            "rolling_summary": _prompt_rolling_summary(state),
            "global_characters": _prompt_global_characters(state),
            "global_settings": _prompt_global_settings(state),
            "archivist_notes": dump_prompt_json(compact_for_prompt(state.get("archivist_notes", {}), limit=12)),
            "retrieved_memories": _prompt_retrieved_memories(state),
            "previous_chapter_summaries": _prompt_previous_summaries(state),
            "template_schema": state.get("template_schema", ""),
            "error_msg": state.get("error_msg", ""),
        },
        temperature=0.25,
    )

    full_output = _draft_to_chapter_script_output(state, output)
    script_data = full_output.model_dump()
    template_data = _chapter_script_to_template(state, script_data)
    script_yaml = to_yaml(template_data)

    logger.info(
        "[Screenwriter] done scenes=%d yaml_chars=%d",
        len(full_output.scenes),
        len(script_yaml),
    )

    return {
        "current_script_data": script_data,
        "current_template_data": template_data,
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
    output = await invoke_structured(
        CRITIC_PROMPT,
        CriticOutput,
        {
            "deterministic_report": dump_prompt_json(deterministic_report),
            "global_characters": _prompt_global_characters(state),
            "global_settings": _prompt_global_settings(state),
            "current_script_data": dump_prompt_json(state.get("current_script_data", {})),
            "current_template_data": dump_prompt_json(state.get("current_template_data", {})),
            "template_schema": state.get("template_schema", ""),
            "current_script_yaml": state.get("current_script_yaml", ""),
        },
        temperature=0.0,
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


async def continuity_critic_node(state: ScriptGraphState) -> dict[str, Any]:
    """Final cross-chapter continuity review before rolling summary updates."""

    logger.info(
        "[ContinuityJudge] start chapter=%s retry=%s",
        state.get("chapter_title") or state.get("chapter_index"),
        state.get("retry_count", 0),
    )

    output = await invoke_structured(
        CONTINUITY_CRITIC_PROMPT,
        ContinuityReviewOutput,
        {
            "chapter_index": state.get("chapter_index", 1),
            "chapter_title": state.get("chapter_title", ""),
            "current_chapter": state.get("current_chapter", ""),
            "rolling_summary": _prompt_rolling_summary(state),
            "previous_chapter_summaries": _prompt_previous_summaries(state),
            "retrieved_memories": _prompt_retrieved_memories(state),
            "global_characters": _prompt_global_characters(state),
            "global_settings": _prompt_global_settings(state),
            "critic_warnings": dump_prompt_json(state.get("critic_warnings", [])),
            "template_schema": state.get("template_schema", ""),
            "current_script_data": dump_prompt_json(state.get("current_script_data", {})),
            "current_script_yaml": state.get("current_script_yaml", ""),
        },
        temperature=0.0,
    )

    review = output.model_dump()
    blocker_instructions = [
        item.get("revision_instruction") or item.get("issue", "")
        for item in review.get("issues", [])
        if item.get("severity") == "blocker"
    ]
    hard_failed = not output.passed or bool(blocker_instructions)
    retry_count = int(state.get("retry_count", 0))
    max_retries = int(state.get("max_retries", 2))
    warnings = [
        *state.get("critic_warnings", []),
        *output.warnings,
        *[
            item.get("issue", "")
            for item in review.get("issues", [])
            if item.get("severity") == "warning" and item.get("issue")
        ],
    ]

    if hard_failed:
        retry_count += 1
        reason = (
            output.error_msg
            or "；".join(item for item in blocker_instructions if item)
            or "当前章节与长期记忆或前文压缩情节存在重大连续性问题。"
        )
        if retry_count >= max_retries:
            logger.warning(
                "[ContinuityJudge] failed but reached max_retries=%d: %s",
                max_retries,
                reason,
            )
            return {
                "error_msg": reason,
                "retry_count": retry_count,
                "critic_warnings": [
                    *warnings,
                    "连续性评判未完全通过，但已达到最大重试次数。",
                ],
                "continuity_warnings": warnings,
                "continuity_review": review,
            }

        logger.warning("[ContinuityJudge] failed retry=%d reason=%s", retry_count, reason)
        return {
            "error_msg": reason,
            "retry_count": retry_count,
            "critic_warnings": warnings,
            "continuity_warnings": warnings,
            "continuity_review": review,
        }

    logger.info("[ContinuityJudge] passed warnings=%d", len(warnings))
    return {
        "error_msg": "",
        "critic_warnings": warnings,
        "continuity_warnings": warnings,
        "continuity_review": review,
    }


async def summarizer_node(state: ScriptGraphState) -> dict[str, Any]:
    """Update rolling summary after a chapter has passed review."""

    logger.info(
        "[Summarizer] start chapter=%s",
        state.get("chapter_title") or state.get("chapter_index"),
    )

    output = await invoke_structured(
        SUMMARIZER_PROMPT,
        RollingSummaryOutput,
        {
            "rolling_summary": _prompt_rolling_summary(state),
            "chapter_title": state.get("chapter_title", ""),
            "current_script_data": dump_prompt_json(state.get("current_script_data", {})),
            "critic_warnings": dump_prompt_json(state.get("critic_warnings", [])),
        },
        temperature=0.15,
    )

    logger.info(
        "[Summarizer] done summary_chars=%d open_threads=%d",
        len(output.rolling_summary),
        len(output.open_threads),
    )

    return {
        "rolling_summary": compact_text_for_prompt(output.rolling_summary, 1800),
        "archivist_notes": {
            **state.get("archivist_notes", {}),
            "latest_summary_metadata": output.model_dump(),
        },
    }


def _deterministic_script_check(state: ScriptGraphState) -> dict[str, Any]:
    """Programmatic guardrail before the LLM critic adds semantic warnings."""

    warnings: list[str] = []
    data = state.get("current_script_data") or {}
    template_data = state.get("current_template_data") or {}

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

    template_error = _template_data_error(template_data)
    if template_error:
        return {
            "passed": False,
            "error_msg": template_error,
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


def _chapter_script_to_template(
    state: ScriptGraphState,
    script_data: dict[str, Any],
) -> dict[str, Any]:
    """Convert internal ChapterScriptOutput into template.yaml's chapter shape."""

    character_profiles = {
        item.get("name"): item
        for item in state.get("global_characters", [])
        if isinstance(item, dict) and item.get("name")
    }
    usage_profiles = {
        item.get("name"): item
        for item in script_data.get("character_usage", [])
        if isinstance(item, dict) and item.get("name")
    }
    scene_character_names = []
    for scene in script_data.get("scenes") or []:
        for name in scene.get("characters") or []:
            if name and name not in scene_character_names:
                scene_character_names.append(name)

    character_names = list(dict.fromkeys([*usage_profiles.keys(), *scene_character_names]))
    characters = []
    for name in character_names:
        usage = usage_profiles.get(name, {})
        profile = character_profiles.get(name, {})
        traits = profile.get("personality") or []
        if isinstance(traits, str):
            trait_text = traits
        else:
            trait_text = "、".join(str(item) for item in traits if item)
        characters.append(
            {
                "姓名": name,
                "身份": usage.get("function_in_chapter") or profile.get("latest_state") or "待确认",
                "性格": trait_text or usage.get("state_change") or "待确认",
            }
        )

    scenes = []
    for index, scene in enumerate(script_data.get("scenes") or [], start=1):
        slugline = scene.get("slugline") or {}
        action_items = scene.get("action") or []
        if isinstance(action_items, list):
            action_text = "\n".join(str(item) for item in action_items if item)
        else:
            action_text = str(action_items)
        dialogue_items = []
        for line in scene.get("dialogue") or []:
            if not isinstance(line, dict):
                continue
            dialogue_items.append(
                {
                    "说话人": line.get("speaker", ""),
                    "情感": line.get("subtext", "") or "待确认",
                    "台词": line.get("line", ""),
                }
            )
        scenes.append(
            {
                "场景序号": index,
                "发生地点": slugline.get("location", "") or "未标明地点",
                "发生时间": slugline.get("time", "") or "unknown",
                "场景人物": scene.get("characters") or [],
                "剧情动作": action_text or scene.get("purpose", "") or "待补写可拍摄动作。",
                "对话": dialogue_items,
            }
        )

    background_lines = [
        state.get("rolling_summary", "").strip(),
        script_data.get("chapter_summary", "").strip(),
    ]
    return {
        "书名": state.get("book_title", "") or "未命名小说",
        "章节": script_data.get("chapter_title") or state.get("chapter_title", ""),
        "背景设定": "\n".join(item for item in background_lines if item) or "待确认",
        "出场人物": characters,
        "场景列表": scenes,
    }


def _template_data_error(template_data: dict[str, Any]) -> str:
    required_keys = ["书名", "章节", "背景设定", "出场人物", "场景列表"]
    for key in required_keys:
        if key not in template_data:
            return f"模板数据缺少字段：{key}"
    if not isinstance(template_data.get("出场人物"), list):
        return "模板数据字段 出场人物 必须是列表。"
    scenes = template_data.get("场景列表")
    if not isinstance(scenes, list) or not scenes:
        return "模板数据字段 场景列表 必须是非空列表。"
    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            return f"模板数据第 {index} 场不是对象。"
        for key in ["场景序号", "发生地点", "发生时间", "场景人物", "剧情动作", "对话"]:
            if key not in scene:
                return f"模板数据第 {index} 场缺少字段：{key}"
    return ""


def _draft_to_chapter_script_output(
    state: ScriptGraphState,
    draft: ScreenwriterDraftOutput,
) -> ChapterScriptOutput:
    """Expand compact LLM screenwriter output into the internal rich schema."""

    character_usage = [
        CharacterUsage(
            name=item.name,
            function_in_chapter=item.identity,
            state_change=item.personality,
        )
        for item in draft.characters
    ]

    settings_seen: dict[str, SettingUsage] = {}
    scenes: list[ScriptScene] = []
    for index, scene in enumerate(draft.scenes, start=1):
        settings_seen.setdefault(
            scene.location,
            SettingUsage(
                name=scene.location,
                visual_or_plot_function=scene.purpose,
            ),
        )
        scenes.append(
            ScriptScene(
                title=f"场景 {scene.scene_number or index}",
                source_ref=SourceReference(
                    chapter_title=state.get("chapter_title", ""),
                    source_span="model_estimated",
                ),
                slugline=Slugline(
                    location=scene.location,
                    time=scene.time,
                    space=scene.space,
                ),
                purpose=scene.purpose,
                conflict=scene.conflict,
                characters=scene.characters,
                action=[scene.action],
                dialogue=[
                    DialogueLine(
                        speaker=line.speaker,
                        line=line.line,
                        subtext=line.emotion,
                    )
                    for line in scene.dialogue
                ],
                visual_notes=[],
                continuity=SceneContinuity(short_term_context=[]),
                revision_note="AI 初稿，需人工复核。",
            )
        )

    return ChapterScriptOutput(
        chapter_title=draft.chapter_title or state.get("chapter_title", ""),
        chapter_logline=draft.chapter_logline,
        chapter_summary=draft.chapter_summary,
        character_usage=character_usage,
        setting_usage=list(settings_seen.values()),
        scenes=scenes,
        continuity_notes=draft.continuity_notes,
        revision_notes=draft.revision_notes,
    )
