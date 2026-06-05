"""Normalize characters, locations, and scenes into stable screenplay IDs."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List

from app.services.llm_output_parser import ensure_list, ensure_string


class StoryRegistry:
    """Maintains stable IDs for people and places across chapters."""

    def __init__(self, memory: Dict[str, Any]):
        self.memory = memory
        self.long_term = memory.setdefault("long_term", {})
        self.characters = self.long_term.setdefault("characters", {})
        self.locations = self.long_term.setdefault("locations", {})

    def character_id(self, name: str, chapter_id: str, payload: Dict[str, Any] | None = None) -> str:
        clean_name = self._clean_name(name)
        if not clean_name:
            clean_name = "待定人物"

        existing = self._find_by_name(self.characters, clean_name)
        if existing:
            character = self.characters[existing]
        else:
            existing = f"char_{len(self.characters) + 1:03d}"
            character = {
                "id": existing,
                "name": clean_name,
                "role": "待定",
                "first_seen": chapter_id,
                "appearances": [],
                "traits": [],
                "goals": [],
                "relationships": [],
                "key_scenes": [],
            }
            self.characters[existing] = character

        if chapter_id not in character["appearances"]:
            character["appearances"].append(chapter_id)

        payload = payload or {}
        self._merge_unique(character, "traits", ensure_list(payload.get("traits")))
        self._merge_unique(character, "goals", ensure_list(payload.get("goals") or payload.get("goal")))
        role_hint = ensure_string(payload.get("role") or payload.get("role_hint"))
        if role_hint and character.get("role") in {"待定", "配角候选"}:
            character["role"] = role_hint[:30]

        return existing

    def location_id(self, name: str, chapter_id: str, payload: Dict[str, Any] | None = None) -> str:
        clean_name = self._clean_location(name)
        if not clean_name:
            clean_name = "未标明地点"

        existing = self._find_by_name(self.locations, clean_name)
        if existing:
            location = self.locations[existing]
        else:
            existing = f"loc_{len(self.locations) + 1:03d}"
            location = {
                "id": existing,
                "name": clean_name,
                "first_seen": chapter_id,
                "visual_identity": "",
                "key_scenes": [],
            }
            self.locations[existing] = location

        visual_identity = ensure_string((payload or {}).get("visual_identity"))
        if visual_identity and not location.get("visual_identity"):
            location["visual_identity"] = visual_identity[:160]

        return existing

    def ingest_chapter_output(self, chapter_id: str, output: Dict[str, Any]) -> None:
        for character in ensure_list(output.get("characters")):
            if isinstance(character, dict):
                self.character_id(character.get("name", ""), chapter_id, character)
            else:
                self.character_id(str(character), chapter_id)

        for location in ensure_list(output.get("locations")):
            if isinstance(location, dict):
                self.location_id(location.get("name", ""), chapter_id, location)
            else:
                self.location_id(str(location), chapter_id)

        self._merge_canon_facts(chapter_id, output)
        self._merge_threads(chapter_id, output)

    def normalize_scenes(self, chapter_id: str, chapter_index: int, output: Dict[str, Any]) -> List[Dict[str, Any]]:
        scenes: list[dict[str, Any]] = []
        raw_scenes = ensure_list(output.get("scenes"))
        if not raw_scenes:
            raw_scenes = [
                {
                    "title": "章节核心场景",
                    "purpose": "保留本章主线并形成可继续打磨的场景初稿",
                    "conflict": ensure_string(output.get("chapter_summary")),
                    "characters": [item.get("name", "") for item in ensure_list(output.get("characters")) if isinstance(item, dict)],
                    "action": [ensure_string(output.get("chapter_summary"))],
                    "dialogue": [],
                }
            ]

        for scene_index, raw in enumerate(raw_scenes, start=1):
            raw = raw if isinstance(raw, dict) else {"title": str(raw)}
            scene_id = f"{chapter_id}_s{scene_index:03d}"
            slugline = raw.get("slugline") if isinstance(raw.get("slugline"), dict) else {}
            location_name = ensure_string(slugline.get("location") or raw.get("location") or "未标明地点")
            location_id = self.location_id(location_name, chapter_id)

            character_ids = []
            for item in ensure_list(raw.get("characters")):
                name = item.get("name", "") if isinstance(item, dict) else str(item)
                character_id = self.character_id(name, chapter_id, item if isinstance(item, dict) else None)
                if character_id not in character_ids:
                    character_ids.append(character_id)
                    self.characters[character_id].setdefault("key_scenes", [])
                    if scene_id not in self.characters[character_id]["key_scenes"]:
                        self.characters[character_id]["key_scenes"].append(scene_id)

            self.locations[location_id].setdefault("key_scenes", [])
            if scene_id not in self.locations[location_id]["key_scenes"]:
                self.locations[location_id]["key_scenes"].append(scene_id)

            scenes.append(
                {
                    "scene_id": scene_id,
                    "source_ref": {
                        "chapter_index": chapter_index,
                        "chapter_id": chapter_id,
                        "chapter_title": ensure_string(raw.get("source_chapter_title")),
                        "source_span": ensure_string(raw.get("source_span"), "model_estimated"),
                    },
                    "slugline": {
                        "location": location_name,
                        "location_id": location_id,
                        "time": ensure_string(slugline.get("time"), "unknown"),
                        "space": ensure_string(slugline.get("space"), "unknown"),
                    },
                    "title": ensure_string(raw.get("title"), f"第{scene_index}场"),
                    "purpose": ensure_string(raw.get("purpose"), "推进章节剧情"),
                    "conflict": ensure_string(raw.get("conflict"), "待编剧强化冲突"),
                    "characters": character_ids,
                    "action": self._string_list(raw.get("action")),
                    "dialogue": self._dialogue_list(raw.get("dialogue"), chapter_id),
                    "visual_notes": self._string_list(raw.get("visual_notes")),
                    "continuity": self._continuity(raw.get("continuity")),
                    "revision_note": ensure_string(
                        raw.get("revision_note"),
                        "AI 初稿，建议人工检查人物动机、对白潜台词和可拍摄性。",
                    ),
                }
            )

        return scenes

    def characters_list(self) -> List[Dict[str, Any]]:
        return [deepcopy(item) for item in self.characters.values()]

    def locations_list(self) -> List[Dict[str, Any]]:
        return [deepcopy(item) for item in self.locations.values()]

    def _dialogue_list(self, value: Any, chapter_id: str) -> List[Dict[str, str]]:
        result: list[dict[str, str]] = []
        for item in ensure_list(value):
            if not isinstance(item, dict):
                continue
            speaker_name = ensure_string(item.get("speaker"))
            speaker_id = self.character_id(speaker_name, chapter_id) if speaker_name else ""
            line = ensure_string(item.get("line"))
            if line:
                result.append(
                    {
                        "speaker": speaker_id,
                        "line": line,
                        "subtext": ensure_string(item.get("subtext"), "待打磨"),
                    }
                )
        return result

    def _continuity(self, value: Any) -> Dict[str, List[str]]:
        raw = value if isinstance(value, dict) else {}
        return {
            "setup": self._string_list(raw.get("setup")),
            "payoff": self._string_list(raw.get("payoff")),
            "short_term_context": self._string_list(raw.get("short_term_context")),
        }

    def _merge_canon_facts(self, chapter_id: str, output: Dict[str, Any]) -> None:
        facts = self.long_term.setdefault("canon_facts", [])
        for fact in self._string_list(output.get("canon_facts")):
            item = {"chapter_id": chapter_id, "fact": fact}
            if item not in facts:
                facts.append(item)

    def _merge_threads(self, chapter_id: str, output: Dict[str, Any]) -> None:
        threads = self.long_term.setdefault("unresolved_threads", [])
        for raw in ensure_list(output.get("unresolved_threads")):
            if isinstance(raw, dict):
                description = ensure_string(raw.get("description"))
                status = ensure_string(raw.get("status"), "open")
            else:
                description = ensure_string(raw)
                status = "open"
            if description and not any(item.get("description") == description for item in threads):
                threads.append(
                    {
                        "thread_id": f"thread_{len(threads) + 1:03d}",
                        "description": description,
                        "opened_in": chapter_id,
                        "status": status,
                    }
                )

    @staticmethod
    def _string_list(value: Any) -> List[str]:
        return [ensure_string(item) for item in ensure_list(value) if ensure_string(item)]

    @staticmethod
    def _merge_unique(target: Dict[str, Any], key: str, values: Iterable[Any]) -> None:
        items = target.setdefault(key, [])
        for value in values:
            text = ensure_string(value)
            if text and text not in items:
                items.append(text[:80])

    @staticmethod
    def _find_by_name(registry: Dict[str, Dict[str, Any]], name: str) -> str:
        for item_id, item in registry.items():
            if item.get("name") == name:
                return item_id
        return ""

    @staticmethod
    def _clean_name(name: str) -> str:
        return ensure_string(name).strip(" ，。！？、：:；;“”\"'")

    @staticmethod
    def _clean_location(name: str) -> str:
        return ensure_string(name).strip(" ，。！？、：:；;“”\"'")
