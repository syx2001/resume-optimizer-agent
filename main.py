"""Web entry point for the resume optimization Agent."""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse
from langgraph.types import Command
from pydantic import BaseModel, Field

from app.agent.graph import compile_graph
from app.agent.state import AgentContext
from app.infrastructure.database.postgres import initialize_database


BASE_DIR = Path(__file__).resolve().parent
FRONTEND_FILE = BASE_DIR / "frontend" / "index.html"


class OptimizeRequest(BaseModel):
    user_id: str = Field(default="demo-user", min_length=1, max_length=200)
    resume_content: str | None = Field(default=None, max_length=100_000)
    job_content: str | None = Field(default=None, max_length=100_000)
    role_title: str | None = Field(default=None, max_length=300)
    language: str = Field(default="auto", max_length=30)
    target_language: str = Field(default="auto", max_length=30)
    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    approval: bool | None = None


class OptimizeResponse(BaseModel):
    session_id: str
    status: str
    original_resume: str | None = None
    plan: dict[str, Any] | None = None
    match_result: dict[str, Any] | None = None
    rag_sources: list[dict[str, Any]] = Field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None


app = FastAPI(title="Resume Optimizer Agent", version="1.0.0")
_graph = None


def get_app_graph():
    """Initialize PostgreSQL once and compile the graph with a checkpointer."""
    global _graph
    if _graph is None:
        resources = initialize_database()
        _graph = compile_graph(
            checkpointer=resources.checkpointer,
            store=resources.store,
        )
    return _graph


def invoke_agent(request: OptimizeRequest) -> dict[str, Any]:
    resume = (request.resume_content or "").strip()
    job = (request.job_content or "").strip()
    if request.approval is None:
        if not job:
            raise HTTPException(status_code=422, detail="请先提供目标岗位描述")

    graph = get_app_graph()
    config = {"configurable": {"thread_id": request.session_id}}
    context = AgentContext(
        user_id=request.user_id,
        thread_id=request.session_id,
    )

    if request.approval is not None:
        return graph.invoke(
            Command(resume={"approved": request.approval}),
            config=config,
            context=context,
        )

    return graph.invoke(
        {
            "resume_input": {"content": resume, "language": request.language},
            "job_input": {"content": job, "role_title": request.role_title},
            "target_language": request.target_language,
            "task_status": "intake",
        },
        config=config,
        context=context,
    )


def stream_agent(request: OptimizeRequest):
    """Stream real LangGraph node updates and match-tool events as SSE."""
    resume = (request.resume_content or "").strip()
    job = (request.job_content or "").strip()
    if request.approval is None and not job:
        raise HTTPException(status_code=422, detail="请先提供目标岗位描述")

    graph = get_app_graph()
    config = {"configurable": {"thread_id": request.session_id}}
    context = AgentContext(user_id=request.user_id, thread_id=request.session_id)
    if request.approval is not None:
        graph_input = Command(resume={"approved": request.approval})
    else:
        graph_input = {
            "resume_input": {"content": resume, "language": request.language},
            "job_input": {"content": job, "role_title": request.role_title},
            "target_language": request.target_language,
            "task_status": "intake",
        }

    for item in graph.stream(
        graph_input,
        config=config,
        context=context,
        stream_mode=["updates", "custom"],
    ):
        if isinstance(item, tuple) and len(item) == 2:
            mode, payload = item
        else:
            mode, payload = "updates", item
        if mode == "custom":
            yield f"data: {json.dumps({'type': 'custom', 'event': payload}, ensure_ascii=False, default=str)}\n\n"
            continue
        if isinstance(payload, dict):
            for node, update in payload.items():
                yield f"data: {json.dumps({'type': 'node', 'node': node, 'update': update}, ensure_ascii=False, default=str)}\n\n"

    final_state = graph.get_state(config).values
    if final_state.get("task_status") == "awaiting_approval":
        response = OptimizeResponse(
            session_id=request.session_id,
            status="approval_required",
            original_resume=final_state.get("resume_input", {}).get("content"),
            plan=final_state.get("optimization_plan"),
            match_result=final_state.get("match_result"),
            rag_sources=final_state.get("rag_sources", []),
        )
    else:
        response = to_response(request.session_id, final_state)
    yield f"data: {json.dumps({'type': 'result', 'result': response.model_dump()}, ensure_ascii=False, default=str)}\n\n"


def to_response(session_id: str, state: dict[str, Any]) -> OptimizeResponse:
    interrupts = state.get("__interrupt__") or []
    if interrupts:
        value = getattr(interrupts[0], "value", interrupts[0])
        value = value if isinstance(value, dict) else {"message": str(value)}
        return OptimizeResponse(
            session_id=session_id,
            status="approval_required",
            original_resume=state.get("resume_input", {}).get("content"),
            plan=value.get("plan"),
            match_result=state.get("match_result"),
            rag_sources=state.get("rag_sources", []),
            result=value,
        )

    result = state.get("final_answer")
    if result:
        return OptimizeResponse(
            session_id=session_id,
            status=result.get("status", state.get("task_status", "completed")),
            original_resume=state.get("resume_input", {}).get("content"),
            match_result=result.get("match_result"),
            rag_sources=state.get("rag_sources", []),
            result=result,
            error=result.get("error"),
        )

    return OptimizeResponse(
        session_id=session_id,
        status=state.get("task_status", "failed"),
        error=state.get("error") or "Agent 未生成结果",
    )


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(FRONTEND_FILE)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/optimize", response_model=OptimizeResponse)
async def optimize(request: OptimizeRequest) -> OptimizeResponse:
    try:
        state = await run_in_threadpool(invoke_agent, request)
        return to_response(request.session_id, state)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent 执行失败：{exc}") from exc


@app.post("/api/optimize/stream")
async def optimize_stream(request: OptimizeRequest) -> StreamingResponse:
    # Validate before StreamingResponse starts sending headers. Raising an
    # HTTPException inside the generator is too late for FastAPI to serialize
    # a normal 4xx response.
    if request.approval is None and not (request.job_content or "").strip():
        raise HTTPException(status_code=422, detail="请先提供目标岗位描述")
    return StreamingResponse(
        stream_agent(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the resume optimizer Agent")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    import uvicorn

    uvicorn.run("main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
