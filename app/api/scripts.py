"""Screenplay conversion endpoints."""

from __future__ import annotations

import json
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from fastapi import Request
from app.core.llm_client import LLMConfigurationError, LLMError
from app.agent.script_graph.llm import GraphLLMConfigurationError, GraphLLMResponseError
from app.models.request import ClearMemoryRequest, ConvertNovelRequest, ConvertProjectRequest
from app.models.response import ApiResponse, ConvertNovelData
from app.services.adaptation_service import AdaptationError, novel_adaptation_service
from app.services.memory_store import memory_store
from app.services.script_project_service import ScriptProjectError, script_project_service
from app.config import settings

router = APIRouter(prefix="/api/scripts")


@router.get("/projects", response_model=ApiResponse)
async def list_projects() -> ApiResponse:
    return ApiResponse(data={"projects": script_project_service.list_projects()})


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


@router.post("/convert-project", response_model=ApiResponse)
async def convert_project(request: ConvertProjectRequest) -> ApiResponse:
    try:
        data = await script_project_service.run_project(request)
        return ApiResponse(data=data)
    except GraphLLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GraphLLMResponseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ScriptProjectError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"project conversion failed: {exc}") from exc


@router.post("/convert-project-stream")
async def convert_project_stream(request: Request, body: ConvertProjectRequest) -> StreamingResponse:
    # 1. 建立中转水池
    stream_queue = asyncio.Queue()
    def send_event_callback(event_data: dict):
        stream_queue.put_nowait(event_data)
    async def background_task():
        # 👇 1. 这个 try 必须留着！用来保护整个长连接任务不会因为崩溃而变成死寂
        try:
            async for event in script_project_service.stream_project_events(body, send_event_callback=send_event_callback):
                stream_queue.put_nowait(event)
            # 全部跑完，发送结束信号
            stream_queue.put_nowait({"event": "pipeline_complete"})
        # 👇 2. 把你朋友写的这些精确拦截器留着，只是把 yield 改成 stream_queue.put_nowait
        except (GraphLLMConfigurationError, ScriptProjectError) as exc:
            stream_queue.put_nowait({"event": "error", "message": str(exc)})
        except GraphLLMResponseError as exc:
            stream_queue.put_nowait({"event": "error", "message": str(exc)})
        except Exception as exc:
            import traceback
            traceback.print_exc()
            stream_queue.put_nowait({"event": "error", "message": f"project conversion failed: {exc}"})
    task = asyncio.create_task(background_task())
    # 4. SSE 抽水机（专门负责把水池里的数据变成流格式送给前端）
    async def event_stream():
        try:
            while True:
                # 🛑 核心防断连机制：前端一旦关掉网页，立刻取消后台大模型任务，拯救你的 Token！
                if await request.is_disconnected():
                    print("⚠️ 检测到前端断开连接，立即熔断后台 LangGraph 任务！")
                    task.cancel()
                    break
                try:
                    # 设定 1 秒超时，方便循环回来检查 is_disconnected
                    event = await asyncio.wait_for(stream_queue.get(), timeout=1.0)
                    # 🌟 关键修改：转换为标准 SSE 格式 (data: {json}\n\n)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    # 遇到结束或错误信号，跳出循环，结束请求
                    if event.get("event") in ["pipeline_complete", "error"]:
                        break
                except asyncio.TimeoutError:
                    continue
        finally:
            # 保底机制：无论因为什么原因退出，都确保后台任务被杀死
            if not task.done():
                task.cancel()   
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream", # 🌟 核心修改：媒体类型改为标准 SSE
    )     


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
