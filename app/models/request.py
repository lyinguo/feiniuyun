"""Request models."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class ConvertNovelRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=80, description="Author/user ID")
    thread_id: str = Field(..., min_length=1, max_length=80, description="Adaptation thread ID")
    novel_text: str = Field(..., min_length=1, description="Novel manuscript text")
    title: Optional[str] = Field(default=None, max_length=120)
    target_format: Literal["web_series", "film", "stage", "audio_drama"] = "web_series"
    adaptation_tone: str = Field(default="现实感、强冲突、可拍摄", max_length=200)
    scene_density: int = Field(default=3, ge=1, le=6)
    chapters_per_episode: int = Field(default=3, ge=1, le=20)
    short_term_window: int = Field(default=2, ge=1, le=8)
    max_chapters: Optional[int] = Field(default=None, ge=3, le=120)

    @field_validator("user_id", "thread_id")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("identifier cannot be empty")
        return value

    @field_validator("novel_text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        value = value.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not value:
            raise ValueError("novel_text cannot be empty")
        return value


class ClearMemoryRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=80)
    thread_id: str = Field(..., min_length=1, max_length=80)
