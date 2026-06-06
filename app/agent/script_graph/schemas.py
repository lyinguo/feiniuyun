"""Pydantic schemas used by the LangGraph screenplay workflow.

These models are designed for LangChain's ``with_structured_output`` API. The
Screenwriter node will ask the model to return ``ChapterScriptOutput`` instead
of free-form text, then the Critic node can validate and convert it to YAML.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


SCRIPT_SCHEMA_VERSION = "1.0"


def normalize_slugline_time(value):
    text = str(value or "").strip().lower()
    aliases = {
        "day": "noon",
        "daytime": "noon",
        "midday": "noon",
        "中午": "noon",
        "正午": "noon",
        "白天": "noon",
        "日间": "noon",
        "清晨": "dawn",
        "凌晨": "dawn",
        "黎明": "dawn",
        "上午": "morning",
        "早晨": "morning",
        "早上": "morning",
        "下午": "afternoon",
        "傍晚": "evening",
        "黄昏": "evening",
        "夜晚": "night",
        "深夜": "night",
        "晚上": "night",
        "未知": "unknown",
        "不明": "unknown",
        "待确认": "unknown",
    }
    return aliases.get(text, text or "unknown")


def normalize_slugline_space(value):
    text = str(value or "").strip().lower().replace(" ", "")
    aliases = {
        "exterior/interior": "interior/exterior",
        "interiorandexterior": "interior/exterior",
        "exteriorandinterior": "interior/exterior",
        "int/ext": "interior/exterior",
        "ext/int": "interior/exterior",
        "indoor/outdoor": "interior/exterior",
        "outdoor/indoor": "interior/exterior",
        "indoor": "interior",
        "inside": "interior",
        "室内": "interior",
        "内景": "interior",
        "outdoor": "exterior",
        "outside": "exterior",
        "室外": "exterior",
        "外景": "exterior",
        "未知": "unknown",
        "不明": "unknown",
        "待确认": "unknown",
    }
    return aliases.get(text, text or "unknown")


class StrictModel(BaseModel):
    """Base model that rejects accidental extra fields from LLM output."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class RelationshipProfile(StrictModel):
    """Relationship between two characters."""

    target_name: str = Field(..., min_length=1, description="Name of the related character")
    relation: str = Field(..., min_length=1, description="Relationship, conflict, or alliance")
    evidence: str = Field(default="", description="Source evidence from the chapter")


class GlobalCharacterProfile(StrictModel):
    """Long-term character archive maintained by the Archivist agent."""

    name: str = Field(..., min_length=1, description="Canonical character name")
    aliases: list[str] = Field(default_factory=list, description="Nicknames or alternate names")
    appearance: str = Field(default="待确认", description="Visual appearance and costume anchors")
    personality: list[str] = Field(default_factory=list, description="Stable personality traits")
    goals: list[str] = Field(default_factory=list, description="Current or long-term dramatic goals")
    relationships: list[RelationshipProfile] = Field(default_factory=list)
    first_seen_chapter: str = Field(default="", description="Chapter title or index where first seen")
    latest_state: str = Field(default="", description="Latest emotional or plot state")
    continuity_notes: list[str] = Field(
        default_factory=list,
        description="Facts that must stay consistent in later chapters",
    )


class GlobalSettingProfile(StrictModel):
    """Long-term world, location, background, costume, and prop setting."""

    name: str = Field(..., min_length=1, description="Setting, location, costume system, or prop name")
    category: Literal["location", "era", "organization", "costume", "prop", "rule", "other"] = "other"
    visual_identity: str = Field(default="待确认", description="What should be visible on screen")
    costume_notes: list[str] = Field(default_factory=list, description="Wardrobe or styling constraints")
    atmosphere: str = Field(default="", description="Mood, sound, light, texture, or production design")
    rules_or_constraints: list[str] = Field(
        default_factory=list,
        description="World rules or continuity constraints",
    )
    first_seen_chapter: str = Field(default="")


class CanonFact(StrictModel):
    """A story fact that should not be contradicted later."""

    fact: str = Field(..., min_length=1)
    evidence: str = Field(default="", description="Short source quote or chapter reference")
    confidence: Literal["high", "medium", "low"] = "medium"


class BackgroundOutput(StrictModel):
    """Parallel pre-analysis focused on setting, period, props, and atmosphere."""

    new_settings: list[GlobalSettingProfile] = Field(default_factory=list)
    updated_settings: list[GlobalSettingProfile] = Field(default_factory=list)
    canon_facts: list[CanonFact] = Field(default_factory=list)
    atmosphere_notes: list[str] = Field(default_factory=list)
    visual_motifs: list[str] = Field(default_factory=list)
    continuity_risks: list[str] = Field(default_factory=list)


class CharacterOutput(StrictModel):
    """Parallel pre-analysis focused on characters."""

    new_characters: list[GlobalCharacterProfile] = Field(default_factory=list)
    updated_characters: list[GlobalCharacterProfile] = Field(default_factory=list)
    character_observations: list[str] = Field(default_factory=list)
    continuity_risks: list[str] = Field(default_factory=list)


class RelationshipEntry(StrictModel):
    """A directed relationship or conflict found in the chapter."""

    source_name: str = Field(..., min_length=1)
    target_name: str = Field(..., min_length=1)
    relation: str = Field(..., min_length=1)
    evidence: str = Field(default="")


class RelationshipOutput(StrictModel):
    """Parallel pre-analysis focused on relationships and conflict lines."""

    relationships: list[RelationshipEntry] = Field(default_factory=list)
    conflict_lines: list[str] = Field(default_factory=list)
    alliance_lines: list[str] = Field(default_factory=list)
    continuity_risks: list[str] = Field(default_factory=list)


class CastingChoice(StrictModel):
    """Screen-facing character design guidance for production and casting."""

    character_name: str = Field(..., min_length=1)
    screen_type: str = Field(default="待确认")
    appearance_anchor: str = Field(default="")
    performance_notes: list[str] = Field(default_factory=list)
    costume_or_makeup: list[str] = Field(default_factory=list)
    evidence: str = Field(default="")


class CastingOutput(StrictModel):
    """Parallel pre-analysis focused on casting, styling, and playable traits."""

    choices: list[CastingChoice] = Field(default_factory=list)
    ensemble_notes: list[str] = Field(default_factory=list)
    continuity_risks: list[str] = Field(default_factory=list)


class ArchivistOutput(StrictModel):
    """Structured output of the Archivist node."""

    new_characters: list[GlobalCharacterProfile] = Field(default_factory=list)
    updated_characters: list[GlobalCharacterProfile] = Field(default_factory=list)
    new_settings: list[GlobalSettingProfile] = Field(default_factory=list)
    updated_settings: list[GlobalSettingProfile] = Field(default_factory=list)
    canon_facts: list[CanonFact] = Field(default_factory=list)
    continuity_risks: list[str] = Field(
        default_factory=list,
        description="Possible contradictions or missing context discovered in this chapter",
    )


class SourceReference(StrictModel):
    """Reference from script scene back to source novel chapter."""

    chapter_title: str = Field(default="")
    source_span: str = Field(
        default="model_estimated",
        description="Paragraph range, opening/middle/end, or other source reference",
    )


class Slugline(StrictModel):
    """Screenplay scene heading."""

    location: str = Field(default="未标明地点")
    time: Literal["dawn", "morning", "noon", "afternoon", "evening", "night", "unknown"] = "unknown"
    space: Literal["interior", "exterior", "interior/exterior", "unknown"] = "unknown"

    @field_validator("time", mode="before")
    @classmethod
    def normalize_time(cls, value):
        return normalize_slugline_time(value)

    @field_validator("space", mode="before")
    @classmethod
    def normalize_space(cls, value):
        return normalize_slugline_space(value)


class DialogueLine(StrictModel):
    """A screenplay dialogue line."""

    speaker: str = Field(..., min_length=1, description="Character name; backend will map it to ID")
    line: str = Field(..., min_length=1)
    subtext: str = Field(default="待打磨", description="Hidden intention or emotional pressure")


class SceneContinuity(StrictModel):
    """Setup/payoff links for long-form continuity."""

    setup: list[str] = Field(default_factory=list, description="Foreshadowing introduced here")
    payoff: list[str] = Field(default_factory=list, description="Foreshadowing paid off here")
    short_term_context: list[str] = Field(
        default_factory=list,
        description="Connections to the rolling summary or previous chapter",
    )


class ScriptScene(StrictModel):
    """One adapted screenplay scene."""

    title: str = Field(..., min_length=1)
    source_ref: SourceReference = Field(default_factory=SourceReference)
    slugline: Slugline = Field(default_factory=Slugline)
    purpose: str = Field(..., min_length=1, description="Dramatic function of the scene")
    conflict: str = Field(..., min_length=1, description="External or internal pressure")
    characters: list[str] = Field(default_factory=list, description="Character names appearing in scene")
    action: list[str] = Field(
        default_factory=list,
        description="Shootable actions; avoid pure psychological narration",
    )
    dialogue: list[DialogueLine] = Field(default_factory=list)
    visual_notes: list[str] = Field(default_factory=list)
    continuity: SceneContinuity = Field(default_factory=SceneContinuity)
    revision_note: str = Field(default="AI 初稿，需人工复核。")

    @field_validator("action")
    @classmethod
    def action_should_not_be_empty(cls, value: list[str]) -> list[str]:
        return value or ["待补写可拍摄动作。"]


class CharacterUsage(StrictModel):
    """How a known character is used in the current chapter script."""

    name: str = Field(..., min_length=1)
    function_in_chapter: str = Field(default="待确认")
    state_change: str = Field(default="", description="How this chapter changes the character")


class SettingUsage(StrictModel):
    """How a known setting is used in the current chapter script."""

    name: str = Field(..., min_length=1)
    visual_or_plot_function: str = Field(default="待确认")


class ChapterScriptOutput(StrictModel):
    """Structured output of the Screenwriter node for one chapter."""

    schema_version: Literal["1.0"] = SCRIPT_SCHEMA_VERSION
    chapter_title: str = Field(default="")
    chapter_logline: str = Field(..., min_length=1, description="One-sentence dramatic summary")
    chapter_summary: str = Field(..., min_length=1, description="Concise plot summary")
    character_usage: list[CharacterUsage] = Field(default_factory=list)
    setting_usage: list[SettingUsage] = Field(default_factory=list)
    scenes: list[ScriptScene] = Field(..., min_length=1)
    continuity_notes: list[str] = Field(default_factory=list)
    revision_notes: list[str] = Field(default_factory=list)


class DraftCharacter(StrictModel):
    """Compact character row matching the user-facing chapter template."""

    name: str = Field(..., min_length=1)
    identity: str = Field(default="待确认")
    personality: str = Field(default="待确认")


class DraftDialogueLine(StrictModel):
    """Compact dialogue row for one scene."""

    speaker: str = Field(..., min_length=1)
    emotion: str = Field(default="待确认")
    line: str = Field(..., min_length=1)


class DraftScene(StrictModel):
    """Compact scene shape used to keep model output short and parseable."""

    scene_number: int = Field(default=1)
    location: str = Field(default="未标明地点")
    time: Literal["dawn", "morning", "noon", "afternoon", "evening", "night", "unknown"] = "unknown"
    space: Literal["interior", "exterior", "interior/exterior", "unknown"] = "unknown"
    characters: list[str] = Field(default_factory=list)
    purpose: str = Field(default="待确认")
    conflict: str = Field(default="待确认")
    action: str = Field(default="待补写可拍摄动作。")
    dialogue: list[DraftDialogueLine] = Field(default_factory=list)

    _normalize_time = field_validator("time", mode="before")(normalize_slugline_time)
    _normalize_space = field_validator("space", mode="before")(normalize_slugline_space)

    @field_validator("characters")
    @classmethod
    def trim_characters(cls, value: list[str]) -> list[str]:
        return [str(item).strip() for item in value if str(item).strip()][:8]

    @field_validator("dialogue")
    @classmethod
    def trim_dialogue(cls, value: list[DraftDialogueLine]) -> list[DraftDialogueLine]:
        return value[:6]


class ScreenwriterDraftOutput(StrictModel):
    """Compact structured output requested from the Screenwriter LLM.

    The backend expands this into ChapterScriptOutput locally. Keeping the LLM
    contract compact prevents long JSON from being truncated by models with a
    4K output limit.
    """

    schema_version: Literal["1.0"] = SCRIPT_SCHEMA_VERSION
    chapter_title: str = Field(default="")
    chapter_logline: str = Field(..., min_length=1)
    chapter_summary: str = Field(..., min_length=1)
    characters: list[DraftCharacter] = Field(default_factory=list)
    scenes: list[DraftScene] = Field(..., min_length=1)
    continuity_notes: list[str] = Field(default_factory=list)
    revision_notes: list[str] = Field(default_factory=list)

    @field_validator("characters")
    @classmethod
    def trim_character_rows(cls, value: list[DraftCharacter]) -> list[DraftCharacter]:
        return value[:16]


class CriticOutput(StrictModel):
    """Structured output of the Critic node."""

    passed: bool = Field(..., description="Whether current_script_yaml satisfies the schema")
    error_msg: str = Field(default="", description="Actionable format or schema error")
    warnings: list[str] = Field(default_factory=list)


class ContinuityIssue(StrictModel):
    """A cross-chapter continuity, grammar, or logic issue."""

    severity: Literal["blocker", "warning"] = "warning"
    issue: str = Field(..., min_length=1)
    evidence: str = Field(default="")
    revision_instruction: str = Field(default="")


class ContinuityReviewOutput(StrictModel):
    """Final continuity review after the chapter script has been generated."""

    passed: bool = Field(..., description="False only for issues that require regenerating the chapter")
    error_msg: str = Field(default="", description="Actionable rewrite instruction when passed is false")
    warnings: list[str] = Field(default_factory=list)
    issues: list[ContinuityIssue] = Field(default_factory=list)


class RollingSummaryOutput(StrictModel):
    """Structured output of the Summarizer node."""

    rolling_summary: str = Field(..., min_length=1)
    key_events: list[str] = Field(default_factory=list)
    open_threads: list[str] = Field(default_factory=list)
    character_state_changes: list[str] = Field(default_factory=list)
