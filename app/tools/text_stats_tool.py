"""Text statistics tool for large-manuscript risk control."""

from __future__ import annotations

import re
from typing import Any, Dict

from app.tools.base import LocalTool


class TextStatsTool(LocalTool):
    name = "chapter_text_stats"
    description = "Reports chapter size and dialogue density."

    def run(self, text: str) -> Dict[str, Any]:
        clean = text or ""
        quote_count = len(re.findall(r"[“\"][^”\"]{2,160}[”\"]", clean))
        sentence_count = len(re.findall(r"[^。！？!?；;]+[。！？!?；;]?", clean))
        return {
            "char_count": len(clean),
            "paragraph_count": len([item for item in re.split(r"\n\s*\n", clean) if item.strip()]),
            "sentence_count": sentence_count,
            "dialogue_quote_count": quote_count,
            "dialogue_density_hint": "high" if quote_count >= 6 else "low",
        }
