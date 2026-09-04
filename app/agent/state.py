# app/agent/state.py agent的共享工作区

#MessagesState里面只有空的message列表
from langgraph.graph import MessagesState
from dataclasses import dataclass
from typing import Literal
TaskStatus = Literal[
    "intake",
    "parsing",
    "analyzing",
    "awaiting_approval",
    "rewriting",
    "validating",
    "completed",
    "blocked",
    "failed",
]


class AgentState(MessagesState, total=False):
    # 用户输入 users
    resume_input: dict  # ResumeInput.model_dump()
    job_input: dict  # JobDescriptionInput.model_dump()
    target_language: str  # 目标输出语言

    # 解析和分析结果 llm
    resume_profile: dict  # ResumeProfile.model_dump()
    job_profile: dict  # JobProfile.model_dump()
    match_result: dict  # MatchResult.model_dump()
    optimization_plan: dict  # OptimizationPlan.model_dump()
    resume_source: Literal[ #判断当前使用的是用户新传入的简历还是数据库里默认的
      "request",
      "saved_default",
    ]
    optimized_resume: str  # 当前候选简历
    changes: list[dict]  # 改了什么，为什么改
    validation_results: list[dict]  # 关键词和格式检查结果

    # 流程控制
    task_status: TaskStatus  # 当前任务状态
    plan_approved: bool  # 用户是否确认优化计划
    repair_attempts: int  # 修复次数
    final_answer: dict  # ResumeOptimizationResult.model_dump()
    error: str  # 失败或阻塞原因
    repair_instructions: list[str]# 下一轮怎么改

    #rag相关
    rag_context: str
    rag_sources: list[dict]

@dataclass
class AgentContext:
    user_id: str
    repository: dict = None
    permissions: list[str] = None
    thread_id: str | None = None
