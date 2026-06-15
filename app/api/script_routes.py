import json
import asyncio
import threading
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import os  # 👈 引入系统路径库
from pathlib import Path
from fastapi import APIRouter, Request

from app.services.novel_converter import run_pipeline

router = APIRouter()

# 定义接收的请求体规范 (更加标准化)
class ConversionRequest(BaseModel):
    json_path: str
    output_dir: str

# @router.post("/run_conversion")
@router.get("/run_conversion")
# @router.get("/run_conversion")
# 2. 核心修改：直接写参数名和类型，千万别用类包装！
async def run_conversion_api(folder_name: str, request: Request):
    """触发剧本转换的 SSE 流式接口"""
    BASE_PROJECT_DIR = Path(__file__).resolve().parents[2]
    
    # 2. 动态拼装输入与输出的 Path 对象（Pathlib 会全自动处理系统的斜杠，不用担心 Windows/Linux 差异）
    # 严格按照你的新规：全量收纳进 data/temp_epubs 目录下
    json_path = BASE_PROJECT_DIR / "data" / "temp_epubs"  / folder_name / "metadata.json"
    output_dir = BASE_PROJECT_DIR / "data" / "temp_epubs" / "scripts" / folder_name

    # 每个请求独立创建一个队列，支持多人并发使用
    stream_queue = asyncio.Queue()
    # 拿到当前的异步事件循环（至关重要）
    loop = asyncio.get_running_loop()

    stop_event = threading.Event()
    def sync_send_event(event_data: dict):
        if stop_event.is_set():
            raise InterruptedError("用户已手动取消任务，线程熔断自杀！")
        loop.call_soon_threadsafe(stream_queue.put_nowait, event_data)

    def background_task():
        """在后台线程运行耗时的图网络推断"""
        try:
            # 启动业务，把线程安全的发送函数塞进去
            # run_pipeline(request.json_path, request.output_dir, send_event_callback=sync_send_event)
            run_pipeline(json_path, output_dir, send_event_callback=sync_send_event)
            if not stop_event.is_set():
                sync_send_event({"type": "pipeline_complete", "status": "success"})
        except InterruptedError:
            print("\n🛑 🛑 🛑 [后端熔断成功] 后台线程检测到前端断开，已强行终止大模型请求！")
        except Exception as e:
            if not stop_event.is_set():
                sync_send_event({"type": "error", "message": str(e)})

    # 启动后台线程
    threading.Thread(target=background_task, daemon=True).start()

    async def event_generator():
        """异步生成器，从队列中抽水，灌给前端"""
        try:
            while True:
                message = None
                # message = await stream_queue.get()
                if await request.is_disconnected():
                    print("⚠️ [哨兵警报] 检测到前端长连接已被用户强行掐断！正在下发熔断指令...")
                    stop_event.set() # 亮起红色信号灯，通知后台 Python 线程自杀
                    break

                try:
                    # 使用 wait_for 做 1 秒超时等待，防止 get() 产生死等阻塞
                    # 这样每隔 1 秒，代码都有机会走到上面去执行一次 is_disconnected 检查
                    message = await asyncio.wait_for(stream_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue # 超时了就进入下一轮循环，顺便触发状态检查
                
                yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
                
                if message.get("type") in ["pipeline_complete", "error"]:
                    break
        finally:
            # 终极安全锁：无论任何原因离开这个生成器（跑完、报错、或者连接异常断开）
            # 都必须强制拉响停止警报，确保后台大模型线程绝对不会变成孤儿野马在后台偷跑！
            if not stop_event.is_set():
                stop_event.set()
                print("🔌 [物理熔断动作] 异步生成器通道关闭，成功将后台大模型红绿灯死锁！")

    # 返回 Server-Sent Events 流
    return StreamingResponse(event_generator(), media_type="text/event-stream")