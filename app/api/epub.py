from fastapi import APIRouter, UploadFile, File
import shutil
import os
from app.services.epub_hand import process_epub_to_dataset # 引入你的函数

router = APIRouter()

@router.post("/parse-epub")
async def parse_epub_endpoint(file: UploadFile = File(...)):
    try:
        # 1. 决定保存路径并保存上传的 epub
        base_dir = "data/temp_epubs"
        os.makedirs(base_dir, exist_ok=True)
        file_path = os.path.join(base_dir, file.filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 2. 为这本小说创建一个专属的输出目录
        folder_name = os.path.splitext(file.filename)[0]
        output_dir = os.path.join(base_dir, folder_name)

        # 3. 调用你的处理函数！它会返回那串极其详尽的 metadata
        book_metadata = process_epub_to_dataset(file_path, output_dir)

        # 4. 把统计结果直接返回给前端浏览器
        return {
            "status": "success", 
            "message": "EPUB解析与拆分完成",
            "data": book_metadata # 前端可以通过 response.data.book_title 拿到书名等
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}