# Resume Optimizer Agent

一个面向求职场景的 Agent Demo：输入个人简历和目标岗位描述后，系统通过可持久化、可暂停、可分支的工作流，完成简历解析、岗位分析、语义匹配、优化计划生成、人工审批、简历重写和质量校验。

本项目更适合用来学习 Agent 应用工程，而不是直接作为生产系统。它集中展示了以下实践：

- 用 LangGraph 编排有状态的多节点 Agent 工作流
- 用 LangGraph Checkpointer 保存会话状态，并支持中断后恢复
- 用 LangGraph Store 保存用户默认简历和 RAG 数据
- 用 RAG 检索简历优化规范，为 Agent 提供可追溯上下文
- 用 LLM 生成 Pydantic 结构化结果，降低自由文本解析成本
- 用工具调用完成关键词覆盖率、语义匹配和知识库检索
- 用 HITL（Human-in-the-Loop）让用户审批优化计划
- 用 Validator + Repair Loop 进行校验、修复和有限次重试

## 技术栈

| 层次 | 技术 | 用途 |
| --- | --- | --- |
| Agent 编排 | LangGraph、LangChain Core | StateGraph、节点、路由、工具和中断恢复 |
| LLM | langchain-openai 兼容接口 | 接入 DeepSeek 或其他 OpenAI-compatible 模型 |
| 结构化输出 | Pydantic 2 | 定义简历、岗位、计划、校验结果的数据契约 |
| RAG | Embedding API、PostgreSQL Store | 文档切分、向量检索和规范引用 |
| 持久化 | PostgreSQL、LangGraph Checkpointer | 保存 Agent checkpoint、Memory 和 RAG 数据 |
| 文档处理 | pypdf、LangChain Text Splitters | 读取 PDF/TXT/Markdown 并切分文本 |
| 基础设施 | 本地启动 PostgreSQL |

## Agent 工作流

~~~text
START
  │
  ▼
intake → load_resume → parse_resume → save_resume → parse_job
                                                        │
                                                        ▼
                                  retrieve_guidelines → match → plan
                                                                     │
                                                                     ▼
                                                            plan_approval
                                                              │       │
                                                     approved ▼       ▼ rejected
                                                            rewrite   blocked
                                                              │
                                                              ▼
                                                           validate
                                                        │      │
                                               repair ◄─┘      └─► finalize
                                                 │
                                                 └──── rewrite（有限次循环）
~~~

关键 Agent 概念对应关系：

- **State**：`app/agent/state.py` 定义跨节点共享的 `AgentState`，保存输入、解析结果、匹配结果、计划、校验结果和任务状态。
- **Node**：`app/agent/node.py` 中每个函数负责一个明确步骤，例如 `parse_resume`、`match`、`rewrite` 和 `validate`。
- **Routing**：`app/agent/routing.py` 根据当前 State 决定下一节点，实现条件分支和修复循环。
- **Context**：`AgentContext` 携带 `user_id` 和 `thread_id` 等运行时上下文。
- **HITL**：`plan_approval` 使用 `interrupt()` 暂停工作流，等待 API 通过 `Command(resume=...)` 恢复。
- **Checkpoint**：API 的 `session_id` 映射为 LangGraph `thread_id`，因此审批请求必须复用同一个 session。

## 项目结构

~~~text
.
├── main.py                         # FastAPI 入口、同步/流式 API
├── frontend/index.html             # 浏览器 Demo
├── app/
│   ├── agent/                      # StateGraph、节点、路由、Prompt
│   ├── core/                       # 环境变量和运行配置
│   ├── infrastructure/ai/         # LLM、Embedding、结构化调用
│   ├── infrastructure/database/   # PostgreSQL Checkpointer / Store
│   ├── memory/                     # 用户默认简历持久化
│   ├── rag/                        # 文档模型、仓储、导入和切分
│   ├── schemas/                    # Pydantic 输入输出模型
│   ├── service/                    # 解析、匹配、优化、校验和修复服务
│   └── tools/                      # Agent 可调用的工具
├── knowledge_base/                 # RAG 原始知识文档
├── scripts/index_knowledge_base.py # 导入并索引知识库
├── scripts/reset_user_data.py      # 清理指定用户数据
├── compose.yaml                    # PostgreSQL 配置
└── app/requirements.txt            # Python 依赖
~~~

## 快速开始

### 1. 准备 Python 环境

需要 Python 3.11 或更高版本。

~~~powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r app/requirements.txt
pip install fastapi uvicorn
~~~

Linux/macOS：

~~~bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt fastapi uvicorn
~~~

### 2. 启动 PostgreSQL

确保 Docker 已安装并运行：

~~~bash
docker compose up -d postgres
~~~

`compose.yaml` 默认创建：

~~~text
数据库：agent_db
用户：agent
密码：agent123
地址：localhost:5432
~~~

### 3. 配置环境变量

在项目根目录创建 `.env`。至少需要配置 PostgreSQL 和两个模型服务：

~~~dotenv
POSTGRES_URI=postgresql://agent:agent123@localhost:5432/agent_db

DEEPSEEK_API_KEY=your_llm_api_key
DEEPSEEK_BASE_URL=https://your-openai-compatible-endpoint/v1
LLM_MODEL=your-chat-model

QWEN_API_KEY=your_embedding_api_key
QWEN_BASE_URL=https://your-embedding-endpoint/v1
EMBEDDING_MODEL=your-embedding-model
EMBEDDING_DIMS=1024

RAG_TOP_K=5
RAG_SCORE_THRESHOLD=0.7
SEMANTIC_MATCH_THRESHOLD=0.55
TOOL_TIMEOUT_SECONDS=30
TOOL_MAX_RETRIES=2
MEMORY_TOP_K=5
MEMORY_SCORE_THRESHOLD=0.7
~~~

`app/infrastructure/ai/llm.py` 使用 `DEEPSEEK_*` 配置 LLM，`app/infrastructure/ai/embedding.py` 使用 `QWEN_*` 配置 Embedding。两者都要求服务兼容 OpenAI API 的调用方式。

### 4. 导入 RAG 知识库

~~~bash
python scripts/index_knowledge_base.py
~~~

脚本默认索引 `knowledge_base/` 下的文档，支持 TXT、Markdown 和 PDF。流程包括：读取文档、切分文本、计算内容 Hash、生成 Embedding、写入 Store；相同内容重复执行时会跳过。

### 5. 启动服务

~~~bash
python main.py
~~~

访问：<http://127.0.0.1:8000/>。也可以使用：

~~~bash
python main.py --host 0.0.0.0 --port 8000 --reload
~~~

## API 使用

### 健康检查

~~~bash
curl http://127.0.0.1:8000/health
~~~

### 发起优化任务

第一次请求需要提供岗位描述；`session_id` 建议由客户端生成并保存：

~~~bash
curl -X POST http://127.0.0.1:8000/api/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo-user",
    "session_id": "demo-session-001",
    "resume_content": "张三，5年后端开发经验，熟悉 Python、FastAPI 和 PostgreSQL。",
    "job_content": "招聘后端工程师，要求熟悉 Python、FastAPI、数据库和微服务。",
    "role_title": "后端工程师",
    "language": "zh",
    "target_language": "zh"
  }'
~~~

如果 Agent 生成了优化计划，响应状态为 `approval_required`，其中包含 `plan`、`match_result` 和 `rag_sources`。

### 审批并恢复工作流

审批请求只需要携带同一个 `session_id`：

~~~bash
curl -X POST http://127.0.0.1:8000/api/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo-user",
    "session_id": "demo-session-001",
    "approval": true
  }'
~~~

`approval: true` 继续执行重写和校验；`approval: false` 会进入 `blocked`，不会继续修改简历。

### SSE 流式接口

~~~bash
curl -N -X POST http://127.0.0.1:8000/api/optimize/stream \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo-user",
    "session_id": "demo-stream-001",
    "resume_content": "我的简历内容",
    "job_content": "目标岗位描述",
    "target_language": "zh"
  }'
~~~

流中包含三类事件：`node`（节点状态更新）、`custom`（工具自定义事件）和 `result`（最终结果）。

## 数据持久化

- **Checkpointer**：以 `session_id` 作为 `thread_id`，保存工作流中断前的 State，支持审批后继续执行。
- **Memory / Store**：用户默认简历保存在命名空间 `("users", user_id, "resume")` 下。
- **RAG Store**：文档元数据位于 `("rag", "documents")`，文本块及向量位于 `("rag", "chunks")`。

清理某个用户的默认简历和用户命名空间数据：

~~~bash
python scripts/reset_user_data.py
python scripts/reset_user_data.py --yes
~~~

该脚本不会删除 RAG 文档或 LangGraph checkpoint。

## 如何阅读 Agent 实现

建议按以下顺序理解代码：

1. 从 `main.py` 查看请求如何进入 Graph，以及 `session_id` 如何用于恢复。
2. 阅读 `app/agent/state.py`，理解 Agent 的共享状态和运行上下文。
3. 阅读 `app/agent/graph.py`，查看节点注册、边和条件路由。
4. 阅读 `app/agent/node.py`，查看每个节点如何调用 Service、Tool 和 LLM。
5. 阅读 `app/agent/routing.py`，理解审批分支、校验分支和修复循环。
6. 阅读 `app/infrastructure/ai/structured.py`，了解 LLM 结构化输出如何映射到 Pydantic 模型。
7. 阅读 `app/rag/ingestion/` 与 `app/tools/knowledge_base.py`，理解 RAG 从导入到检索的完整链路。

## 当前限制

- 这是学习型 Demo，尚未覆盖完整鉴权、限流、监控、生产级日志和多租户隔离。
- 工具超时和重试配置已预留，但不代表所有工具都具备完整的生产级重试策略。
- PostgreSQL、LLM 和 Embedding 服务必须先正确配置，服务启动时会按需初始化数据库资源。
