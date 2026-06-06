"""Memory merge helpers for script graph agents."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from app.agent.script_graph.schemas import (
    ArchivistOutput,
    GlobalCharacterProfile,
    GlobalSettingProfile,
)

PROMPT_TEXT_LIMIT = 700
PROMPT_NESTED_LIST_LIMIT = 6
PROMPT_DICT_ITEM_LIMIT = 24

MERGED_LIST_FIELD_LIMITS = {
    "aliases": 8,
    "personality": 8,
    "goals": 8,
    "relationships": 12,
    "continuity_notes": 12,
    "costume_notes": 8,
    "rules_or_constraints": 10,
}
HEAD_PRESERVED_FIELDS = {"aliases", "personality", "goals"}


def merge_archivist_output(
    *,
    global_characters: list[dict[str, Any]],
    global_settings: list[dict[str, Any]],
    archivist_output: ArchivistOutput,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Merge Archivist output into global character and setting archives."""

    characters = deepcopy(global_characters or [])
    settings = deepcopy(global_settings or [])

    character_events: list[str] = []
    setting_events: list[str] = []

    for profile in [
        *archivist_output.new_characters,
        *archivist_output.updated_characters,
    ]:
        event = _merge_profile(
            records=characters,
            profile=profile,
            list_fields=[
                "aliases",
                "personality",
                "goals",
                "relationships",
                "continuity_notes",
            ],
            scalar_fields=[
                "appearance",
                "first_seen_chapter",
                "latest_state",
            ],
        )
        character_events.append(f"{event}: {profile.name}")

    for profile in [
        *archivist_output.new_settings,
        *archivist_output.updated_settings,
    ]:
        event = _merge_profile(
            records=settings,
            profile=profile,
            list_fields=[
                "costume_notes",
                "rules_or_constraints",
            ],
            scalar_fields=[
                "category",
                "visual_identity",
                "atmosphere",
                "first_seen_chapter",
            ],
        )
        setting_events.append(f"{event}: {profile.name}")

    notes = {
        "canon_facts": [fact.model_dump() for fact in archivist_output.canon_facts],
        "continuity_risks": archivist_output.continuity_risks,
        "character_events": character_events,
        "setting_events": setting_events,
    }

    return characters, settings, notes


def compact_for_prompt(value: Any, limit: int = 40) -> Any:
    """Limit large archives before passing them to a prompt.

    The graph stores rich long-term archives, but prompts only need compact
    working context. This keeps later chapters from carrying ever-growing
    relationship lists and long free-text fields into every model call.
    """

    return _compact_value(value, limit=limit, depth=0)


def compact_text_for_prompt(value: Any, limit: int = 1600) -> str:
    """Clip long direct text while keeping both the beginning and recent tail."""

    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    marker = "\n...\n"
    if limit <= len(marker):
        return text[:limit]
    head_size = max(0, limit // 3)
    tail_size = max(0, limit - head_size - len(marker))
    return f"{text[:head_size].rstrip()}{marker}{text[-tail_size:].lstrip()}"


def _compact_value(value: Any, *, limit: int, depth: int) -> Any:
    if isinstance(value, list):
        item_limit = limit if depth == 0 else PROMPT_NESTED_LIST_LIMIT
        return [
            _compact_value(item, limit=limit, depth=depth + 1)
            for item in value[-item_limit:]
        ]
    if isinstance(value, dict):
        items = list(value.items())[:PROMPT_DICT_ITEM_LIMIT]
        return {
            key: _compact_value(item, limit=limit, depth=depth + 1)
            for key, item in items
        }
    if isinstance(value, str):
        return compact_text_for_prompt(value, PROMPT_TEXT_LIMIT)
    return value


def _merge_profile(
    *,
    records: list[dict[str, Any]],
    profile: GlobalCharacterProfile | GlobalSettingProfile,
    list_fields: Iterable[str],
    scalar_fields: Iterable[str],
) -> str:
    incoming = _cap_record_lists(profile.model_dump(), list_fields)
    existing = _find_by_name(records, incoming["name"])

    if existing is None:
        records.append(incoming)
        return "created"

    for field in scalar_fields:
        value = incoming.get(field)
        if _is_meaningful(value):
            existing[field] = value

    for field in list_fields:
        existing_values = existing.setdefault(field, [])
        for item in incoming.get(field) or []:
            if not _contains_equivalent(existing_values, item):
                existing_values.append(item)
        existing[field] = _cap_list_field(field, existing_values)

    return "updated"


def _cap_record_lists(record: dict[str, Any], list_fields: Iterable[str]) -> dict[str, Any]:
    for field in list_fields:
        record[field] = _cap_list_field(field, list(record.get(field) or []))
    return record


def _cap_list_field(field: str, values: list[Any]) -> list[Any]:
    limit = MERGED_LIST_FIELD_LIMITS.get(field)
    if not limit or len(values) <= limit:
        return values
    if field in HEAD_PRESERVED_FIELDS:
        return values[:limit]
    return values[-limit:]


def _find_by_name(records: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for record in records:
        if record.get("name") == name:
            return record
        aliases = record.get("aliases") or []
        if name in aliases:
            return record
    return None


def _contains_equivalent(items: list[Any], item: Any) -> bool:
    if item in items:
        return True
    if isinstance(item, dict):
        return any(isinstance(existing, dict) and existing == item for existing in items)
    return False


def _is_meaningful(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        stripped = value.strip()
        return bool(stripped and stripped != "待确认")
    if isinstance(value, list):
        return bool(value)
    return True
