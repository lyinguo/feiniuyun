大体架构

---
技术栈             (暂定，写到README.md)
编排控制层：LangChain + LangGraph（架构）
组件：RAG、Chroma/Milvus 向量数据库、LangGraph State（长短期记忆）
任务持久化调度：用户标识、任务流水 ID、SQLite/Redis 检查点
工具解耦层：MCP  工具调用
前端可视化：Vue3  

---