"""Health endpoints."""

from fastapi import APIRouter

from app.config import settings
from app.models.response import ApiResponse, HealthData

router = APIRouter()


@router.get("/api/health", response_model=ApiResponse)
async def health() -> ApiResponse:
    return ApiResponse(
        data=HealthData(
            service=settings.app_name,
            version=settings.app_version,
            llm_configured=settings.llm_configured,
        ).model_dump()
    )
