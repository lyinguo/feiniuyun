"""Memory merge helpers for script graph agents."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from app.agent.script_graph.schemas import (
    ArchivistOutput,
    GlobalCharacterProfile,
    GlobalSettingProfile,
)


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
    """Limit large archives before passing them to a prompt."""

    if isinstance(value, list):
        return value[-limit:]
    return value


def _merge_profile(
    *,
    records: list[dict[str, Any]],
    profile: GlobalCharacterProfile | GlobalSettingProfile,
    list_fields: Iterable[str],
    scalar_fields: Iterable[str],
) -> str:
    incoming = profile.model_dump()
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

    return "updated"


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

