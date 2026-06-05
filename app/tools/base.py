"""Base classes for local adaptation tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class LocalTool(ABC):
    name: str
    description: str

    @abstractmethod
    def run(self, text: str) -> Dict[str, Any]:
        """Return structured context for a chapter."""
