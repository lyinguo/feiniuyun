import json
import os
import re
from pathlib import Path
from openai import OpenAI

# 1. 配置 LLM 客户端
# 安全提示：建议将 API Key 放到环境变量中，避免代码泄露
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY", "sk-a8c9847e99e94beb9e9cb2a267acbbd4"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
)

def parse_llm_output(full_text: str):
    """通过正则提取剧本正文、短期记忆和长期记忆更新"""
    script_match = re.search(r'<script>(.*?)</script>', full_text, re.DOTALL)
    short_match = re.search(r'<short_term>(.*?)</short_term>', full_text, re.DOTALL)
    long_match = re.search(r'<long_term>(.*?)</long_term>', full_text, re.DOTALL)

    return {
        "script": script_match.group(1).strip() if script_match else "解析正文失败，请检查LLM输出格式。",
        "short_term": short_match.group(1).strip() if short_match else "无短期记忆",
        "long_term": long_match.group(1).strip() if long_match else "无长期记忆"
    }

def run_pipeline(json_path: str, output_dir: str):
    # 将输入的 json_path 转换为 Path 对象
    json_path_obj = Path(json_path)
    
    # 【核心修复】：获取 JSON 文件所在的父目录
    # 如果 json_path 是 "..\data\temp_epubs\output_trimmed\metadata.json"
    # base_dir 就会自动解析为 "..\data\temp_epubs\output_trimmed"
    base_dir = json_path_obj.parent

    # 2. 读取项目 JSON 配置文件
    with open(json_path_obj, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    chapters = data.get("chapters", [])
    book_title = data.get("book_title", "未命名作品")
    print(f"📖 成功加载项目：《{book_title}》，共计 {len(chapters)} 章。\n")

    # 3. 初始化记忆变量
    current_long_term_memory = "目前暂无长期记忆。请在首次生成时提取核心人物设定和背景。"
    current_short_term_memory = "目前暂无短期记忆，这是故事的第一章。"

    # 创建输出目录
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # 4. 核心 For 循环闭环
    for chapter in chapters:
        idx = chapter["logical_index"]
        title = chapter["original_title"]
        rel_file_path = chapter["file_path"] # JSON 里存的相对路径，例如 "./chapter_002_001.txt"

        print(f"{'='*50}\n🚀 正在处理: {title} (索引: {idx})\n{'='*50}")

        # 【核心修复】：将 JSON 所在目录与 txt 的相对路径进行智能拼接，并转换为绝对路径
        actual_file_path = (base_dir / rel_file_path).resolve()

        # 读取小说章节原文本
        if not actual_file_path.exists():
            print(f"⚠️ 警告：找不到文件 {actual_file_path}，已跳过。")
            continue
            
        with open(actual_file_path, 'r', encoding='utf-8') as f:
            chapter_content = f.read()

        # 构造 Prompt
        system_prompt = """你是一个专业的影视编剧。你的任务是将小说章节改编为剧本格式，并维护系统的短期与长期记忆以保证连贯性。
请严格按照以下 XML 格式输出你的回复：
<script>
此处撰写改编后的剧本正文（包含场景描述、人物对话、动作指导等）
</script>
<short_term>
此处撰写给下一章的【短期记忆备忘录】（例如：本章结尾时的场景位置、人物当前情绪状态、刚刚埋下的悬念等）
</short_term>
<long_term>
此处撰写更新后的【长期记忆】（整合之前的长期记忆，补充本章新出现的关键人物设定、核心世界观和主线剧情线索，抛弃冗余细节）
</long_term>"""

        user_prompt = f"""
【全局长期记忆】：
{current_long_term_memory}

【上一章传递的短期记忆】：
{current_short_term_memory}

【本章待改编小说内容】（{title}）：
{chapter_content}
"""

        # 5. 调用 LLM 并流式输出
        response = client.chat.completions.create(
            model="deepseek-v4-flash", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            stream=True,
            temperature=0.7
        )

        print(">> LLM 正在生成内容 (流式输出):\n")
        full_response = ""
        for chunk in response:
            if chunk.choices[0].delta.content is not None:
                text_chunk = chunk.choices[0].delta.content
                print(text_chunk, end="", flush=True)
                full_response += text_chunk
        print("\n\n>> 本章生成结束，正在解析并保存数据...\n")

        # 6. 解析结构化输出
        parsed_data = parse_llm_output(full_response)
        script_text = parsed_data["script"]
        
        # 更新记忆状态，准备喂给下一章
        current_short_term_memory = parsed_data["short_term"]
        current_long_term_memory = parsed_data["long_term"]

        # 7. 保存文件（剧本正文与记忆备份）
        script_file = out_path / f"chapter_{idx:03d}_script.txt"
        memory_file = out_path / f"chapter_{idx:03d}_memory.json"

        # 保存剧本
        with open(script_file, 'w', encoding='utf-8') as f:
            f.write(script_text)
            
        # 短期和长期记忆随章节一同保存
        with open(memory_file, 'w', encoding='utf-8') as f:
            json.dump({
                "short_term_memory_for_next": current_short_term_memory,
                "updated_long_term_memory": current_long_term_memory,
                "raw_full_output": full_response
            }, f, ensure_ascii=False, indent=2)

        print(f"✅ 剧本已保存至: {script_file}")
        print(f"✅ 记忆已存档至: {memory_file}\n")

if __name__ == "__main__":
    # 保持你传入的绝对或相对路径不变
    run_pipeline(
        json_path=r"..\data\temp_epubs\output_trimmed\metadata.json", 
        output_dir=r"./output_scripts"
    )