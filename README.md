# AI 小说转剧本工具

这是一个“前端 + Python 后端 + 真实大模型调用”的 AI 辅助剧本创作工具。输入 3 章以上小说文本后，后端按章节调用大模型，生成结构化剧本 YAML 初稿，并维护 `user_id/thread_id` 隔离的长短期记忆。

## 项目结构

```text
app/
  api/                 FastAPI 路由
  core/                LLM 客户端、可选 MCP 接入
  agent/script_graph/  LangGraph 多 Agent 剧本生成工作流
  models/              请求/响应模型
  services/            分章、记忆、生成编排、Schema 校验
  tools/               本地 tool/skill 上下文
docs/
  yaml_schema.md       剧本 YAML Schema 与设计原因
  architecture.md      架构、长短期记忆、大文本处理说明
src/app.js             前端交互，调用 Python 后端
index.html             前端页面
samples/sample_novel.txt
```

## 安装与配置

```bash
pip install -r requirements.txt
```

复制 `.env.example` 为 `.env`，填入真实模型配置：

```text
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-max
LLM_API_KEY=你的真实 API Key
```

也兼容 OpenAI-compatible 常见变量名：

```text
OPENAI_BASE_URL=https://api.siliconflow.cn/v1
OPENAI_API_KEY=你的真实 API Key
LLM_MODEL=MiniMaxAI/MiniMax-M2.5
```

如果没有 `LLM_API_KEY`、`OPENAI_API_KEY` 或 `DASHSCOPE_API_KEY`，后端会返回配置错误，不会用假数据伪装生成成功。

## 启动

```bash
uvicorn app.main:app --reload --port 8000
```

访问：

```text
http://127.0.0.1:8000
```

也可以直接打开 `index.html`，前端会默认请求 `http://127.0.0.1:8000`。

## API

### 健康检查

```http
GET /api/health
```

### 小说转剧本

```http
POST /api/scripts/convert
```

请求示例：

```json
{
  "user_id": "author_demo",
  "thread_id": "adaptation_001",
  "novel_text": "第一章 ...\n\n第二章 ...\n\n第三章 ...",
  "title": "雨灯档案",
  "target_format": "web_series",
  "adaptation_tone": "现实感、强冲突、可拍摄",
  "scene_density": 3,
  "chapters_per_episode": 3,
  "short_term_window": 2
}
```

返回数据包含：

- `yaml`：可编辑剧本 YAML。
- `script`：结构化对象。
- `memory_snapshot`：该 `user_id/thread_id` 的记忆快照。
- `stats`：章节数、场景数、人物数、地点数、模型调用次数。

## LangGraph 多 Agent 工作流

新增的多 Agent 工作流位于 `app/agent/script_graph`：

```text
Archivist 档案员
  -> 更新 global_characters / global_settings
  -> 提取 canon_facts 和 continuity_risks

Screenwriter 编剧
  -> 使用 with_structured_output(ChapterScriptOutput)
  -> 生成当前章节结构化剧本和 YAML

Critic 审查员
  -> 程序化 Schema 校验 + LLM 审查
  -> 失败则 error_msg + retry_count，并回到 Screenwriter

Summarizer 总结员
  -> 更新 rolling_summary
  -> 为下一章提供滚动记忆
```

图结构：

```text
Archivist -> Screenwriter -> Critic
                         ^      |
                         |      | failed && retry_count < max_retries
                         +------+
                                |
                                | passed 或达到最大重试
                                v
                           Summarizer -> END
```

运行真实模型 Demo：

```bash
D:\anaconda\envs\super_biz311\python.exe -m app.agent.script_graph.demo --input samples/sample_novel.txt --output data/script_graph_demo_output.yaml
```

这个 Demo 会真实调用 `.env` 中配置的大模型。

## 怎么理解题目的难点

这个题不是做一个“看起来像剧本的页面”，而是要处理长篇小说改编中的上下文问题。

核心理解：

- 前端只负责输入、参数、`user_id/thread_id`、展示和下载。
- Python 后端负责真实大模型调用、记忆、校验和 YAML 生成。
- 长小说不能一次性塞给模型，而是按章节处理。
- 短期记忆保留最近 N 章，负责临近剧情衔接。
- 长期记忆保存人物、地点、事实、伏笔，负责全书一致性。
- YAML Schema 是 AI 初稿与人工打磨之间的结构化交换格式。

## 测试

```bash
python -m unittest discover tests_py
python -m py_compile app/main.py app/core/llm_client.py app/services/adaptation_service.py
```

测试不会调用大模型，只检查核心非 LLM 模块。
=======
大体架构

---
技术栈             (暂定，写到README.md)
编排控制层：LangChain + LangGraph（架构）
组件：RAG、Chroma/Milvus 向量数据库、LangGraph State（长短期记忆）
任务持久化调度：用户标识、任务流水 ID、SQLite/Redis 检查点
工具解耦层：MCP  工具调用
前端可视化：Vue3  

---
