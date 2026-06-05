"""Tool that exposes the screenplay YAML schema to the LLM."""

from __future__ import annotations

from typing import Any, Dict

from app.tools.base import LocalTool


class YamlSchemaTool(LocalTool):
    name = "screenplay_yaml_schema"
    description = "Summarizes the required screenplay YAML structure."

    def run(self, text: str) -> Dict[str, Any]:
        return {
            "schema_version": "1.0",
            "required_layers": [
                "project",
                "source",
                "memory.short_term",
                "memory.long_term",
                "characters",
                "locations",
                "script.episodes.acts.scenes",
                "review_notes",
            ],
            "scene_required_fields": [
                "scene_id",
                "source_ref",
                "slugline",
                "purpose",
                "conflict",
                "characters",
                "action",
                "dialogue",
                "continuity",
            ],
        }
