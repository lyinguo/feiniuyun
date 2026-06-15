"""FastAPI application entry point."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import health, scripts, epub, script_routes
from app.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="AI-assisted novel to screenplay YAML tool",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(scripts.router)
    app.include_router(epub.router, prefix="/api")
    app.include_router(script_routes.router, prefix="/api/v1", tags=["剧本转换"])
    root = Path(__file__).resolve().parents[1]
    src_dir = root / "src"
    if src_dir.exists():
        app.mount("/src", StaticFiles(directory=src_dir), name="src")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(root / "index.html")

    @app.get("/styles.css")
    async def styles() -> FileResponse:
        return FileResponse(root / "styles.css")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
