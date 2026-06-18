import json
import os
import re
from pathlib import Path
from typing import TypedDict
from openai import OpenAI
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

# ==========================================
# 新增：自动寻找并加载项目中的 .env 文件
# ==========================================
load_dotenv(r'../.env')

# 1. 客户端配置 (全部从环境变量/ .env 读取)
# 如果 .env 中没有对应的值，会使用后面的 fallback 默认值防崩溃
client = OpenAI(
    api_key=os.getenv("LLM_API_KEY", "未配置API_KEY"),
    base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
)
# 提取模型名称作为全局变量
CURRENT_MODEL = os.getenv("LLM_MODEL", "gpt-3.5-turbo")

# 读取 Prompt 配置
with open("prompts_config.json", "r", encoding="utf-8") as f:
    PROMPTS = json.load(f)

# 2. 定义状态 (State)
class AgentState(TypedDict):
    chapter_title: str
    chapter_content: str
    short_term_memory: str
    long_term_memory: str
    raw_response: str
    script_output: str

# 3. 定义节点函数 (Nodes)

def generate_script_node(state: AgentState) -> AgentState:
    """节点 1：调用 LLM 生成内容并流式输出"""
    print(f"\n>> 正在生成 [{state['chapter_title']}] 的内容 (流式输出):\n")
    
    user_prompt = PROMPTS["user_prompt_template"].format(
        long_term=state["long_term_memory"],
        short_term=state["short_term_memory"],
        title=state["chapter_title"],
        content=state["chapter_content"]
    )

    response = client.chat.completions.create(
        model=CURRENT_MODEL, # 使用 .env 中配置的模型名
        messages=[
            {"role": "system", "content": PROMPTS["system_prompt"]},
            {"role": "user", "content": user_prompt}
        ],
        stream=True,
        temperature=0.7
    )

    full_response = ""
    for chunk in response:
        if chunk.choices[0].delta.content is not None:
            text_chunk = chunk.choices[0].delta.content
            print(text_chunk, end="", flush=True)
            full_response += text_chunk
    
    print("\n\n>> 本章生成结束。")
    return {"raw_response": full_response}

def parse_and_update_memory_node(state: AgentState) -> AgentState:
    """节点 2：解析 XML 标签，更新记忆并剥离剧本"""
    full_text = state["raw_response"]
    
    script_match = re.search(r'<script>(.*?)</script>', full_text, re.DOTALL)
    short_match = re.search(r'<short_term>(.*?)</short_term>', full_text, re.DOTALL)
    long_match = re.search(r'<long_term>(.*?)</long_term>', full_text, re.DOTALL)

    script = script_match.group(1).strip() if script_match else "解析失败，原始内容:\n" + full_text
    new_short_term = short_match.group(1).strip() if short_match else state["short_term_memory"]
    new_long_term = long_match.group(1).strip() if long_match else state["long_term_memory"]

    return {
        "script_output": script,
        "short_term_memory": new_short_term,
        "long_term_memory": new_long_term
    }

# 4. 构建 LangGraph 工作流
workflow = StateGraph(AgentState)

workflow.add_node("generate", generate_script_node)
workflow.add_node("parse", parse_and_update_memory_node)

workflow.set_entry_point("generate")
workflow.add_edge("generate", "parse")
workflow.add_edge("parse", END)

app = workflow.compile()

# 5. 主执行闭环
def run_pipeline(json_path: str, output_dir: str):
    json_path_obj = Path(json_path)
    base_dir = json_path_obj.parent
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    with open(json_path_obj, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    chapters = data.get("chapters", [])
    
    current_state = {
        "short_term_memory": "目前暂无短期记忆，这是故事的第一章。",
        "long_term_memory": "目前暂无长期记忆。请在首次生成时提取核心设定。"
    }

    for chapter in chapters:
        idx = chapter["logical_index"]
        title = chapter["original_title"]
        actual_file_path = (base_dir / chapter["file_path"]).resolve()

        if not actual_file_path.exists():
            continue
            
        with open(actual_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        print(f"{'='*50}\n🚀 运行 Graph: {title} (使用模型: {CURRENT_MODEL})\n{'='*50}")

        current_state["chapter_title"] = title
        current_state["chapter_content"] = content

        final_state = app.invoke(current_state)

        current_state["short_term_memory"] = final_state["short_term_memory"]
        current_state["long_term_memory"] = final_state["long_term_memory"]

        script_file = out_path / f"chapter_{idx:03d}_script.txt"
        memory_file = out_path / f"chapter_{idx:03d}_memory.json"

        with open(script_file, 'w', encoding='utf-8') as f:
            f.write(final_state["script_output"])
            
        with open(memory_file, 'w', encoding='utf-8') as f:
            json.dump({
                "short_term": final_state["short_term_memory"],
                "long_term": final_state["long_term_memory"]
            }, f, ensure_ascii=False, indent=2)

        print(f"✅ 完成并存档。\n")

if __name__ == "__main__":
    run_pipeline(r"..\data\temp_epubs\output_trimmed\metadata.json", r"./output_scripts")