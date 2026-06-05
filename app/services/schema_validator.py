"""Runtime validation for generated screenplay YAML data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Set


@dataclass
class ValidationReport:
    valid: bool
    errors: List[str]
    warnings: List[str]


class ScreenplaySchemaValidator:
    """Lightweight structural validator.

    Pydantic models are useful for API payloads, but generated scripts need
    cross-reference checks: scene characters must exist, IDs must be unique,
    and source chapter references must be in range.
    """

    def validate(self, data: Dict[str, Any]) -> ValidationReport:
        errors: list[str] = []
        warnings: list[str] = []

        self._require(data, "schema_version", errors)
        self._require(data, "project", errors)
        self._require(data, "source", errors)
        self._require(data, "memory", errors)
        self._require(data, "characters", errors)
        self._require(data, "locations", errors)
        self._require(data, "script", errors)

        source = data.get("source") or {}
        chapter_count = int(source.get("chapter_count") or 0)
        if chapter_count < 1:
            errors.append("source.chapter_count must be >= 1.")
        elif chapter_count < 3:
            warnings.append(
                "source.chapter_count is less than 3; treating input as chapter-by-chapter processing."
            )

        character_ids = self._unique_ids(data.get("characters") or [], "characters", errors)
        location_ids = self._unique_ids(data.get("locations") or [], "locations", errors)
        scene_ids: set[str] = set()

        episodes = ((data.get("script") or {}).get("episodes")) or []
        if not episodes:
            errors.append("script.episodes must not be empty.")

        for episode in episodes:
            for act in episode.get("acts") or []:
                for scene in act.get("scenes") or []:
                    scene_id = scene.get("scene_id")
                    if not scene_id:
                        errors.append("scene.scene_id is required.")
                    elif scene_id in scene_ids:
                        errors.append(f"duplicate scene_id: {scene_id}")
                    else:
                        scene_ids.add(scene_id)

                    source_ref = scene.get("source_ref") or {}
                    chapter_index = int(source_ref.get("chapter_index") or 0)
                    if chapter_index < 1 or chapter_index > chapter_count:
                        errors.append(
                            f"{scene_id or 'scene'} source_ref.chapter_index out of range."
                        )

                    slugline = scene.get("slugline") or {}
                    location_id = slugline.get("location_id")
                    if location_id and location_id not in location_ids:
                        errors.append(f"{scene_id} references unknown location {location_id}.")

                    for character_id in scene.get("characters") or []:
                        if character_id not in character_ids:
                            errors.append(f"{scene_id} references unknown character {character_id}.")

                    for dialogue in scene.get("dialogue") or []:
                        speaker = dialogue.get("speaker")
                        if speaker and speaker not in character_ids:
                            errors.append(f"{scene_id} dialogue references unknown speaker {speaker}.")

                    if not scene.get("purpose"):
                        warnings.append(f"{scene_id} has no purpose.")
                    if not scene.get("conflict"):
                        warnings.append(f"{scene_id} has no conflict.")

        return ValidationReport(valid=not errors, errors=errors, warnings=warnings)

    @staticmethod
    def _require(data: Dict[str, Any], key: str, errors: List[str]) -> None:
        if key not in data:
            errors.append(f"{key} is required.")

    @staticmethod
    def _unique_ids(items: List[Dict[str, Any]], label: str, errors: List[str]) -> Set[str]:
        ids: set[str] = set()
        for item in items:
            item_id = item.get("id")
            if not item_id:
                errors.append(f"{label} item is missing id.")
            elif item_id in ids:
                errors.append(f"duplicate {label} id: {item_id}")
            else:
                ids.add(item_id)
        return ids


screenplay_schema_validator = ScreenplaySchemaValidator()
