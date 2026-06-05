"""Response models."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    code: int = Field(default=200)
    message: str = Field(default="success")
    data: Optional[Any] = None


class ConvertNovelData(BaseModel):
    user_id: str
    thread_id: str
    yaml: str
    script: Dict[str, Any]
    diagnostics: List[str]
    stats: Dict[str, Any]
    memory_snapshot: Dict[str, Any]


class HealthData(BaseModel):
    service: str
    version: str
    llm_configured: bool
