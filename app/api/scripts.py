"""Screenplay conversion endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.llm_client import LLMConfigurationError, LLMError
from app.models.request import ClearMemoryRequest, ConvertNovelRequest
from app.models.response import ApiResponse, ConvertNovelData
from app.services.adaptation_service import AdaptationError, novel_adaptation_service
from app.services.memory_store import memory_store
from app.config import settings

router = APIRouter(prefix="/api/scripts")


@router.post("/convert", response_model=ApiResponse)
async def convert_novel(request: ConvertNovelRequest) -> ApiResponse:
    try:
        data = await novel_adaptation_service.convert(request)
        return ApiResponse(data=ConvertNovelData(**data).model_dump())
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (AdaptationError, LLMError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"conversion failed: {exc}") from exc


@router.get("/memory/{user_id}/{thread_id}", response_model=ApiResponse)
async def get_memory(user_id: str, thread_id: str) -> ApiResponse:
    data = memory_store.snapshot(
        user_id,
        thread_id,
        settings.default_short_term_window,
    )
    return ApiResponse(data=data)


@router.post("/memory/clear", response_model=ApiResponse)
async def clear_memory(request: ClearMemoryRequest) -> ApiResponse:
    success = memory_store.clear(request.user_id, request.thread_id)
    return ApiResponse(
        data={
            "success": success,
            "user_id": request.user_id,
            "thread_id": request.thread_id,
        }
    )
