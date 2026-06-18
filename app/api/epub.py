from fastapi import APIRouter, UploadFile, File, Form
import shutil
import os

router = APIRouter()

@router.post("/parse-epub")
async def parse_epub_endpoint(file: UploadFile = File(...), max_chars: int = Form(20000)):
    try:
        from app.services.epub_hand import process_epub_to_dataset # 引入你的函数

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
        book_metadata = process_epub_to_dataset(file_path, output_dir, max_chars_per_chunk=max_chars)

        # 4. 把统计结果直接返回给前端浏览器
        return {
            "status": "success", 
            "message": "EPUB解析与拆分完成",
            "data": book_metadata, # 前端可以通过 response.data.book_title 拿到书名等
            "folder_name": folder_name
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/get-chapter")
async def get_chapter_endpoint(folder: str, file_name: str):
    try:
        # 防御性编程：防止路径穿越漏洞
        if ".." in folder or ".." in file_name:
            return {"status": "error", "message": "非法路径"}
            
        # file_name 前端传过来可能是 "./chapter_001.txt"，把 "./" 去掉
        clean_file_name = file_name.replace("./", "")
        
        file_path = os.path.join("data/temp_epubs", folder, clean_file_name)
        
        if not os.path.exists(file_path):
            return {"status": "error", "message": "未找到该章节的文本文件"}
            
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        return {"status": "success", "content": content}
    except Exception as e:
        return {"status": "error", "message": str(e)}
