# 架构说明：AI 小说转剧本工具

本项目已从纯前端演示改为“前端 + Python 后端 + 真实大模型调用”的结构。

## 分层

```text
前端 index.html / src/app.js
  - 接收小说文本
  - 接收 user_id / thread_id
  - 做轻量章节预览
  - 调用后端 API
  - 展示 YAML、记忆状态、场景预览

FastAPI app/main.py
  - 提供静态页面
  - 注册 health 和 scripts API

API app/api/scripts.py
  - POST /api/scripts/convert
  - GET /api/scripts/memory/{user_id}/{thread_id}
  - POST /api/scripts/memory/clear

Core app/core
  - llm_client.py：真实 OpenAI-compatible 大模型调用
  - mcp_client.py：可选 MCP 工具元数据接入

Services app/services
  - chapter_splitter.py：小说分章
  - adaptation_service.py：转换编排
  - memory_store.py：长短期记忆持久化
  - prompt_builder.py：Prompt 构造
  - story_registry.py：人物/地点/场景 ID 归一化
  - schema_validator.py：YAML Schema 引用校验
  - yaml_builder.py：YAML 序列化

Tools app/tools
  - schema_tool.py：把 YAML Schema 要点注入模型上下文
  - text_stats_tool.py：章节规模和对白密度统计
```

## 长小说怎么处理

长小说的核心问题不是“能不能一次读完”，而是上下文管理。

本项目采用章节级流水线：

```text
整本小说
  -> 分章
  -> 每章调用一次大模型生成结构化 JSON
  -> 更新短期记忆
  -> 更新长期故事圣经
  -> 归一化人物/地点 ID
  -> 组装 episode/act/scene
  -> 校验 Schema
  -> 输出 YAML
```

这样做的原因：

1. 单章比整本更容易放入模型上下文。
2. 失败时可以定位到具体章节。
3. 人物、地点、伏笔由长期记忆保存，不依赖模型每次“记住全部”。
4. 短期记忆只保留最近 N 章，控制提示词长度。

## 短期记忆

短期记忆位于：

```text
memory.short_term.recent_chapters
```

它保存最近 N 章：

- `chapter_id`
- `title`
- `summary`
- `scene_ids`
- `active_characters`

作用是保证相邻章节衔接，例如上一章谁在场、刚发生了什么、哪些场景刚结束。

## 长期记忆

长期记忆位于：

```text
memory.long_term
```

它保存：

- `logline`
- `canon_facts`
- `characters`
- `locations`
- `unresolved_threads`

作用是防止长篇改编时设定漂移。例如人物目标、地点视觉特征、已经确认的事实、未解决伏笔。

## user_id 和 thread_id

前端必须传：

```json
{
  "user_id": "author_demo",
  "thread_id": "adaptation_001"
}
```

后端把记忆保存到：

```text
data/memory/{user_id}/{thread_id}.json
```

含义：

- `user_id` 区分作者或登录用户。
- `thread_id` 区分同一作者的不同改编项目、不同版本或不同会话。

这样可以避免多个用户、多个小说项目之间记忆串线。

## 真实大模型调用

后端通过 `app/core/llm_client.py` 调用 OpenAI-compatible Chat Completions API。

必要环境变量：

```text
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-max
LLM_API_KEY=真实 API Key
```

如果没有 `LLM_API_KEY`，后端会返回 503 配置错误，不会使用假数据伪装成功。

## MCP / Tool / Skill 理解

当前项目内置了本地 tool 层：

- YAML Schema tool：告诉模型必须产出什么结构。
- Text stats tool：告诉模型章节长度、段落数、对白密度。

`app/core/mcp_client.py` 预留了 MCP 工具元数据接入。当前不会强行调用外部 MCP 工具，因为小说改编的主链路更适合先稳定生成和校验。后续可以把人物知识库、世界观设定库、风格词典等做成 MCP 工具或本地 skill 注入 prompt。

## 鲁棒性策略

1. 无 API Key 直接失败，不产生假结果。
2. 模型输出必须是 JSON object，后端解析失败会返回错误。
3. 生成结果必须通过 Schema 引用校验。
4. 记忆按 user/thread 隔离，并用原子写入保存。
5. 单次输入有上限，避免一次请求拖垮服务。
6. 人物和地点由后端统一分配 ID，避免模型输出 ID 漂移。
