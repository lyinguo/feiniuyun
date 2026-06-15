import json
import os
import re
import uuid
from pathlib import Path
from typing import TypedDict, Any
import chromadb
from openai import OpenAI
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
import asyncio

# 1. 基础配置加载
load_dotenv(r'D:\SYJ\work_study\python\Novel2Script_AI\feiniuyun\.env')

client = OpenAI(
    api_key=os.getenv("LLM_API_KEY", "未配置API_KEY"),
    base_url=os.getenv("LLM_BASE_URL", "[https://api.openai.com/v1](https://api.openai.com/v1)")
)
CURRENT_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
PROMPT_PATH = PROJECT_ROOT / "configs" / "prompts_config.json"
with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    PROMPTS = json.load(f)

# 创建一个消息队列，用于在 LangGraph 和 FastAPI 之间传递数据
# stream_queue = asyncio.Queue()
# ==========================================
# 初始化 ChromaDB：创建人物和场所两个记忆池
# ==========================================
DB_PATH = PROJECT_ROOT / "data" / "chroma_db"
DB_PATH.mkdir(parents=True, exist_ok=True)
chroma_client = chromadb.PersistentClient(path=str(DB_PATH))
char_collection = chroma_client.get_or_create_collection(name="novel_characters")
location_collection = chroma_client.get_or_create_collection(name="novel_locations")

# 2. 定义状态 (State)
class AgentState(TypedDict):
    chapter_idx: int
    chapter_title: str
    chapter_content: str
    
    story_progress: str
    
    retrieved_characters: str 
    retrieved_locations: str
    
    raw_response: str
    script_output: Any # 改为 Any，因为现在它是 JSON 列表或字典
    
    new_characters: list 
    new_locations: list 
    is_valid_json: bool
    retry_count: int
    send_event: Any
# 3. 定义节点函数 (Nodes)

def retrieve_memory_node(state: AgentState) -> AgentState:
    """节点 0：双路检索人物与场所"""
    print(f"\n🔍 [检索节点] 正在检索 [{state['chapter_title']}] 的历史相关记忆...")
    query_text = state["chapter_content"][:1000]
    
    def query_collection_with_metadata(collection, query_str, limit=5):
        if collection.count() == 0:
            return "暂无历史记录。"
        results = collection.query(query_texts=[query_str], n_results=min(limit, collection.count()))
        if results['documents'] and results['documents'][0]:
            docs = results['documents'][0]
            metas = results['metadatas'][0]
            formatted_lines = []
            for doc, meta in zip(docs, metas):
                chapter_source = meta.get("chapter", "未知章节")
                formatted_lines.append(f"- [{chapter_source}] {doc}")
            return "\n".join(formatted_lines)
        return "未检索到高度相关的线索。"

    char_facts = query_collection_with_metadata(char_collection, query_text, limit=4)
    location_facts = query_collection_with_metadata(location_collection, query_text, limit=4)
    
    print("-" * 40)
    print("💡 召回历史人物线索：\n" + char_facts)
    print("-" * 40)
    print("💡 召回历史场所线索：\n" + location_facts)
    print("-" * 40)
    state["send_event"]({
        "type": "retrieval_done",
        "retrieved_characters": char_facts,
        "retrieved_locations": location_facts
    })
    return {
        "retrieved_characters": char_facts,
        "retrieved_locations": location_facts
    }


def generate_script_node(state: AgentState) -> AgentState:
    """节点 1：生成剧本"""
    print(f"\n>> [生成节点] 正在生成 [{state['chapter_title']}] 的内容 (流式输出):\n")
    # ==========================================
    # 🌟 新增逻辑：在这里进行临时的段落切分与 ID 打标
    # 这样只影响喂给 LLM 的提示词，不影响外层的 state 和 ChromaDB 检索
    # ==========================================
    raw_content = state["chapter_content"]
    paragraphs = [p.strip() for p in raw_content.split('\n') if p.strip()]
    
    chunked_lines = []
    for i, p_text in enumerate(paragraphs, start=1):
        chunked_lines.append(f"[p_{i}] {p_text}")
        
    tagged_content = "\n".join(chunked_lines)
    # ==========================================
    state["send_event"]({
        "type": "node_start",
        "node": "generate_script",
        "chapter_title": state['chapter_title'],
        "story_progress": state['story_progress'],
        "retrieved_characters": state['retrieved_characters']
    })
    user_prompt = PROMPTS["user_prompt_template"].format(
        retrieved_characters=state["retrieved_characters"],
        retrieved_locations=state["retrieved_locations"],
        story_progress=state["story_progress"],
        title=state["chapter_title"],
        # content=state["chapter_content"]
        content=tagged_content
    )

    response = client.chat.completions.create(
        model=CURRENT_MODEL,
        messages=[
            {"role": "system", "content": PROMPTS["system_prompt"]},
            {"role": "user", "content": user_prompt}
        ],
        stream=True,
        temperature=0.7
    )

    full_response = ""
    full_reasoning = ""
    print("开始回复")
    for chunk in response:
        delta = chunk.choices[0].delta
        # 1. 🔍 捕捉并分流“思考过程” (Reasoning / Thinking Line)
        # 不同的模型提供方字段略有不同，推荐使用 .get() 或 hasattr 兼容防护
        reasoning_chunk = getattr(delta, "reasoning_content", None)
        if reasoning_chunk:
            # 实时喂给前端的 SSE 传送带
            print(reasoning_chunk, end="", flush=True) 
            state["send_event"]({
                "type": "reasoning",
                "content": reasoning_chunk
            })
            full_reasoning += reasoning_chunk
        # 2. 🎥 捕捉并分流“最终剧本正文” (Final Content Line)
        # 注意：这里用平行的 if，并且去掉了 continue，这样就算同一个 chunk 里同时有思考和正文，也不会漏掉！
        if getattr(delta, "content", None) is not None:
            text_chunk = delta.content
            print(text_chunk, end="", flush=True) 
            state["send_event"]({
                "type": "token",
                "content": text_chunk
            })
            full_response += text_chunk
    
    state["send_event"]({
        "type": "node_finish",
        "node": "generate_script"
    })
    return {"raw_response": full_response}


def parse_and_update_memory_node(state: AgentState) -> AgentState:
    """节点 2：解析输出，如果 JSON 损坏则触发拦截"""
    full_text = state["raw_response"]
    
    script_match = re.search(r'<script>(.*?)</script>', full_text, re.DOTALL)
    progress_match = re.search(r'<story_progress>(.*?)</story_progress>', full_text, re.DOTALL)
    char_match = re.search(r'<new_characters>(.*?)</new_characters>', full_text, re.DOTALL)
    loc_match = re.search(r'<new_locations>(.*?)</new_locations>', full_text, re.DOTALL)

    raw_script_text = script_match.group(1).strip() if script_match else "[]"
    cleaned_script_text = re.sub(r'^```json\s*|\s*```$', '', raw_script_text, flags=re.MULTILINE).strip()
    
    is_valid = False
    try:
        script_json = json.loads(cleaned_script_text)
        is_valid = True
    except json.JSONDecodeError as e:
        # 如果解析失败，保存原始文本和报错信息，供纠错节点使用
        script_json = {"raw_text": raw_script_text, "error_msg": str(e)}

    new_progress = progress_match.group(1).strip() if progress_match else state["story_progress"]
    
    def extract_list(match_obj):
        if not match_obj:
            return []
        text = match_obj.group(1).strip()
        return [f.strip("- *") for f in text.split('\n') if f.strip("- *")]

    new_chars_list = extract_list(char_match)
    new_locs_list = extract_list(loc_match)

    def insert_to_chroma(collection, data_list, chapter_title, chapter_idx):
        if data_list:
            ids = [uuid.uuid4().hex for _ in data_list]
            metadatas = [{"chapter": chapter_title, "logical_index": chapter_idx} for _ in data_list]
            collection.add(documents=data_list, metadatas=metadatas, ids=ids)

    # === 核心逻辑：只有 JSON 完全合法，才将设打入向量数据库 ===
    if is_valid:
        insert_to_chroma(char_collection, new_chars_list, state["chapter_title"], state["chapter_idx"])
        insert_to_chroma(location_collection, new_locs_list, state["chapter_title"], state["chapter_idx"])
        print(f"\n📥 [解析节点] 剧本合法！已录入向量库: {len(new_chars_list)} 人物，{len(new_locs_list)} 场所。")
    else:
        current_retry = state.get('retry_count', 0)
        print(f"\n⚠️ [解析节点] JSON 语法损坏，已拦截入库 (准备第 {current_retry + 1} 次重试)...")

    return {
        "script_output": script_json,
        "story_progress": new_progress,
        "new_characters": new_chars_list,
        "new_locations": new_locs_list,
        "is_valid_json": is_valid
    }
def correct_json_node(state: AgentState) -> AgentState:
    """节点 3：【新增】专门修复 JSON 语法的格式化助手"""
    retry_count = state.get("retry_count", 0) + 1
    print(f"\n🔧 [纠错节点] 启动格式修复手术 (第 {retry_count} 次修复尝试)...")

    broken_text = state["script_output"]["raw_text"]
    error_msg = state["script_output"]["error_msg"]

    # 专门针对纠错的 Prompt
    fix_prompt = f"""
                你是一个 JSON 语法修复专家。下面这段剧本 JSON 在解析时报错了，报错信息是：{error_msg}。
                请你仅修复引号转义、缺失逗号、括号不匹配等语法错误。
                【绝对禁止】修改、增加或删除里面的任何中文剧情内容和台词。
                请将修复后的内容以合法的 JSON 数组格式输出，并用 ```json 包裹：
                {broken_text}
                """

    response = client.chat.completions.create(
        model=CURRENT_MODEL,
        messages=[{"role": "user", "content": fix_prompt}],
        temperature=0.1 # 极低温度，拒绝模型发散思维
    )
    
    fixed_script = response.choices[0].message.content
    
    # 将修复后的 script 内容替换回 raw_response 中，准备流回解析节点
    new_raw_response = re.sub(
        r'<script>.*?</script>', 
        f'<script>\n{fixed_script}\n</script>', 
        state["raw_response"], 
        flags=re.DOTALL
    )

    return {
        "raw_response": new_raw_response, 
        "retry_count": retry_count
    }
def check_json_validity(state: AgentState):
    if state.get("is_valid_json"):
        return "success" # 没问题，直接结束
    elif state.get("retry_count", 0) < 3: 
        return "retry" # 有问题，且重试次数小于 3，去抢救
    else:
        return "give_up" # 抢救了3次依然失败，放弃治疗

async def event_generator():
    """这是一个异步生成器，不断从队列里拿数据，按 SSE 标准格式发给前端"""
    while True:
        # 等待队列里出现新数据
        message = await stream_queue.get()
        
        # 如果收到结束信号，停止发送
        if message.get("type") == "pipeline_complete":
            yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
            break
            
        # SSE 的标准格式是 "data: {...}\n\n"
        yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
# 4. 构建 LangGraph 工作流
workflow = StateGraph(AgentState)

workflow.add_node("retrieve", retrieve_memory_node)
workflow.add_node("generate", generate_script_node)
workflow.add_node("parse", parse_and_update_memory_node)
workflow.add_node("correct", correct_json_node)

workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "generate")
workflow.add_edge("generate", "parse")
workflow.add_conditional_edges(
    "parse",
    check_json_validity,
    {
        "success": END,       # 合法，流程结束
        "retry": "correct",   # 不合法，流向纠错节点
        "give_up": END        # 放弃治疗，带着报错强行结束
    }
)
workflow.add_edge("correct", "parse")

app = workflow.compile()

# 5. 主执行闭环
def run_pipeline(json_path: str, output_dir: str, send_event_callback=None):
    json_path_obj = Path(json_path)
    base_dir = json_path_obj.parent
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    with open(json_path_obj, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    raw_chapters = data.get("chapters", [])
    if send_event_callback is None:
        send_event_callback = lambda x: None
        
    # ==========================================
    # 🌟 核心修改 1：在后端也进行“拍平”操作
    # ==========================================
    flattened_tasks = []
    for ch in raw_chapters:
        idx = ch.get("logical_index")
        base_title = ch.get("original_title", "未知章节")

        if ch.get("is_chunked") and ch.get("chunks"):
            chunks = ch["chunks"]
            total_chunks = len(chunks)
            for chunk in chunks:
                flattened_tasks.append({
                    "logical_index": idx,
                    "sub_index": chunk.get("sub_index"),
                    "title": f"{base_title} ({chunk.get('sub_index')}/{total_chunks})",
                    "file_path": chunk.get("file_path")
                })
        else:
            flattened_tasks.append({
                "logical_index": idx,
                "sub_index": 0, # 0 表示无分块
                "title": base_title,
                "file_path": ch.get("file_path")
            })

    current_state = {
        "story_progress": "故事刚刚开始，暂无前情提要。",
        "send_event": send_event_callback
    }

    # ==========================================
    # 🌟 核心修改 2：遍历拍平后的独立任务列表
    # ==========================================
    for task in flattened_tasks:
        idx = task["logical_index"]
        sub_idx = task["sub_index"]
        title = task["title"]
        file_path_str = task.get("file_path")

        if not file_path_str:
            continue

        actual_file_path = (base_dir / file_path_str).resolve()

        if not actual_file_path.exists():
            print(f"⚠️ 文件不存在，跳过: {actual_file_path}")
            continue
            
        with open(actual_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        print(f"\n{'='*60}\n🚀 开始处理: {title}\n{'='*60}")

        send_event_callback({
            "type": "chapter_start", 
            "title": title
        })
        current_state["chapter_idx"] = idx
        current_state["chapter_title"] = title
        current_state["chapter_content"] = content

        final_state = app.invoke(current_state)

        current_state["story_progress"] = final_state["story_progress"]

        # ==========================================
        # 🌟 核心修改 3：动态生成防覆盖的文件名
        # ==========================================
        # 如果是分块任务，文件名会带上 sub_idx，比如 chapter_004_1_script.json
        suffix = f"_{sub_idx}" if sub_idx > 0 else ""
        script_file = out_path / f"chapter_{idx:03d}{suffix}_script.json"
        memory_file = out_path / f"chapter_{idx:03d}{suffix}_memory.json"

        # 1. 保存结构化的剧本 JSON
        with open(script_file, 'w', encoding='utf-8') as f:
            json.dump(final_state["script_output"], f, ensure_ascii=False, indent=4)
            
        # 2. 保存审查日志 (Audit Log)
        with open(memory_file, 'w', encoding='utf-8') as f:
            json.dump({
                "_audit_note": "此文件仅供人类审查 Debug，不参与图网络状态流转",
                "1_inputs_from_rag": {
                    "retrieved_characters": final_state.get("retrieved_characters", ""),
                    "retrieved_locations": final_state.get("retrieved_locations", "")
                },
                "2_outputs_for_next_chapter": {
                    "story_progress": final_state["story_progress"],
                },
                "3_outputs_saved_to_db": {
                    "new_characters_extracted": final_state.get("new_characters", []),
                    "new_locations_extracted": final_state.get("new_locations", [])
                }
            }, f, ensure_ascii=False, indent=4)

        print(f"✅ 完成并生成结构化剧本: {script_file}\n")



# if __name__ == "__main__":
#     run_pipeline(r"..\data\temp_epubs\output_trimmed\metadata.json", r"./output_scripts")