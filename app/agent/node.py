from typing import Any

from pydantic import ValidationError
from app.agent.state import AgentState
from app.schemas import ResumeInput,JobDescriptionInput,JobProfile,ResumeProfile,MatchResult,OptimizationPlan,RewriteResult,ValidationResult,ResumeOptimizationResult,ResumeChange
from app.service import ResumeJobMatcher,ResumeOptimizer,ResumeParser,ResumeRepairService,ResumeValidator,JobParser
from langgraph.types import interrupt
from langgraph.runtime import Runtime
from app.memory.repository import ResumeRepository
from app.memory.service import ResumeService
from app.tools.knowledge_base import search_knowledge_base
from langgraph.config import get_stream_writer
resume_parser = ResumeParser()
job_parser = JobParser()
matcher = ResumeJobMatcher()
optimizer = ResumeOptimizer()
validator = ResumeValidator()
repair_service = ResumeRepairService()

def load_user_resume_node(state:AgentState, runtime:Runtime):

    # 从状态中获取本次请求传入的简历输入，为空则赋值空字典
    current = state.get("resume_input") or {}

    # 判断：如果本次请求已经携带有效的简历内容，标记简历来源为「用户本次请求传入」直接返回
    if current.get("content", "").strip():
        return {"resume_source": "request"}
    
    #创建实例
    service = ResumeService(ResumeRepository(runtime.store))
    # 请求没有携带简历，通过runtime上下文拿到当前登录用户ID，查询用户保存的默认简历
    stored = service.get_default(runtime.context.user_id)

    # 用户没有保存默认简历，返回失败状态，提示用户先提交简历
    if stored is None:
        return {
            "task_status": "failed",
            "error": "当前用户没有默认简历，请先提交简历。",
        }
    print("load_resume")
    # 读取到用户保存的默认简历，回填到state，标记简历来源为「用户已保存的默认简历」
    return {
        "resume_input": {
            "content": stored.content,      # 简历文本内容
            "language": stored.language,    # 简历语言版本
        },
        "resume_profile": stored.profile,  # 简历解析后的结构化个人档案
        "resume_source": "saved_default",  # 简历来源标记：使用本地保存默认简历
    }

def save_resume_node(state:AgentState, runtime:Runtime)-> dict[str, Any]:
    """
    要保存:
    Resume_id-从service、
    user_id-runtime.context.user_id、
    content-state.resume_input、
    profile-state.resume_profile、
    source_name
    """
    resume_input = ResumeInput.model_validate(
          state["resume_input"]
      )

    resume_profile = ResumeProfile.model_validate(
        state["resume_profile"]
    )
    service = ResumeService(
          ResumeRepository(runtime.store)
      )

    service.save_default(
        user_id=runtime.context.user_id,
        resume_input=resume_input,
        resume_profile=resume_profile,
    )
    return {
        "resume_source": "request",
        "resume_saved": True,
    }


def retrieve_guidelines_node(
      state: AgentState,
  ) -> dict[str, Any]:
      job_profile = JobProfile.model_validate(
          state["job_profile"]
      )

      query = (
          "请检索与以下岗位相关的简历优化规范：\n"
          f"岗位职责：{job_profile.responsibilities}\n"
          f"必需技能：{job_profile.required_skills}\n"
          f"关键词：{job_profile.keywords}\n"
          "重点关注岗位匹配、ATS、事实边界、"
          "AI Agent 项目表达和简历校验规则。"
      )

      try:
          result = search_knowledge_base.invoke(
              {
                  "query": query,
                  "top_k": 5,
              }
          )

          sources = result.get("sources", [])

          rag_context = "\n\n".join(
              source.get("content", "")
              for source in sources
              if source.get("content")
          )

          rag_sources = [
              {
                  "source": source.get("source"),
                  "page_number": source.get("page_number"),
                  "score": source.get("score"),
              }
              for source in sources
          ]

          return {
              "rag_context": rag_context,
              "rag_sources": rag_sources,
          }

      except Exception as exc:
          # 求职 Demo 中，RAG 失败不应该阻断整个简历优化流程
          return {
              "rag_context": "",
              "rag_sources": [],
              "error": f"知识库检索失败：{exc}",
          }
#检查输入内容是否规范，并且规范化
def intake_node(state: AgentState) -> dict[str, Any]:
    """
    简历优化任务的入口节点。

    主要职责：
    1. 检查简历输入和职位描述输入是否存在；
    2. 使用 Pydantic 数据模型校验统一规范输入；
    3. 初始化本轮任务的流程控制字段；

    输入 State:
        resume_input:
            ResumeInput.model_dump() 形式的字典。
        job_input:
            JobDescriptionInput.model_dump() 形式的字典。
        target_language: 默认中文

    输出 State:
        resume_input:
            校验并归一化后的 ResumeInput 字典。
        job_input:
            校验并归一化后的 JobDescriptionInput 字典。
        target_language:
            归一化后的目标语言。
        task_status:
            成功时设置为 "intake"，失败时设置为 "failed"。
        repair_attempts:
            初始化为 0。
        error:
            成功时清空；失败时记录可读错误信息。
    """

    resume_data = state.get("resume_input")
    job_data = state.get("job_input")

    # ---------- 基础存在性检查 ----------

    if resume_data is None:
        return {
            "task_status": "failed",
            "error": "缺少简历输入 resume_input。",
        }

    if job_data is None:
        return {
            "task_status": "failed",
            "error": "缺少职位描述输入 job_input。",
        }

    # ---------- Pydantic 数据校验 ----------
    try:
        resume_input = ResumeInput.model_validate(resume_data)
        job_input = JobDescriptionInput.model_validate(job_data)

    except ValidationError as exc:
        return {
            "task_status": "failed",
            "error": f"输入数据格式校验失败：{exc}",
        }

    # ---------- 业务级空内容检查  清洗数据----------
    resume_content = resume_input.content.strip()
    job_content = job_input.content.strip()

    if not job_content:
        return {
            "task_status": "failed",
            "error": "职位描述内容不能为空。",
        }

    # ---------- 目标语言归一化 ----------
    target_language = state.get("target_language", "auto")

    if not isinstance(target_language, str):
        return {
            "task_status": "failed",
            "error": "target_language 必须是字符串。",
        }

    target_language = target_language.strip().lower()

    if not target_language:
        target_language = "auto"

    # ---------- 返回本轮任务的初始化状态 ----------

    return {
        "resume_input": resume_input.model_dump(),
        "job_input": job_input.model_dump(),
        "target_language": target_language,
        "task_status": "intake",
        "repair_attempts": 0,
        "final_answer": {},
        "optimized_resume": "",
        "changes": [],
        "validation_results": [],
        "repair_instructions": [],
        "plan_approved": False,
        "error": "",
    }

#通过llm结构化输出：个人简历、技能列表、工作经历、项目经历
def parse_resume_node(
    state: AgentState,
) -> dict:
    """
    将原始简历内容解析为结构化 ResumeProfile。
    读取：
        resume_input
    写入：
        resume_profile
        task_status
    """

    try:
        resume_input = ResumeInput.model_validate(
            state["resume_input"]
        )
        profile = resume_parser.parse(
            content=resume_input.content,
            language=resume_input.language,
        )
        if not isinstance(profile, ResumeProfile):
            profile = ResumeProfile.model_validate(profile)
        return {
            "resume_profile": profile.model_dump(),
            "task_status": "parsing",
            "error": "",
        }

    except Exception as exc:
        return {
            "task_status": "failed",
            "error": (
                f"简历解析失败："
                f"{type(exc).__name__}: {exc}"
            ),
        }

#将state里面的job_input转变为岗位职责、必需技能、JD关键词
def parse_job_node(
    state: AgentState,
) -> dict:
    """
    将原始职位描述解析为结构化 JobProfile。
    读取：
        job_input
    写入：
        job_profile
    """
    try:
        job_input = JobDescriptionInput.model_validate(
            state["job_input"]
        )

        profile = job_parser.parse(
            content=job_input.content,
            role_title=job_input.role_title,
        )

        if not isinstance(profile, JobProfile):
            profile = JobProfile.model_validate(profile)

        return {
            "job_profile": profile.model_dump(),
            "error": "",
        }

    except Exception as exc:
        return {
            "task_status": "failed",
            "error": (
                f"职位描述解析失败："
                f"{type(exc).__name__}: {exc}"
            ),
        }

#对比jobprofile和resumeprofile的区别，输出岗位匹配分数、匹配要求、缺失要求
def match_node(
    state: AgentState,
) -> dict:
    """
    分析当前简历与目标岗位之间的匹配程度。

    读取：
        resume_profile
        job_profile

    写入：
        match_result
        task_status
    """
    try:
        resume_profile = ResumeProfile.model_validate(
            state["resume_profile"]
        )

        job_profile = JobProfile.model_validate(
            state["job_profile"]
        )

        try:
            stream_writer = get_stream_writer()
        except Exception:
            stream_writer = None

        def emit_match_tool(event: dict) -> None:
            if stream_writer:
                stream_writer(event)

        result = matcher.match(
            resume_profile=resume_profile,
            job_profile=job_profile,
            rag_context=state.get("rag_context", ""),
            event_callback=emit_match_tool,
        )

        if not isinstance(result, MatchResult):
            result = MatchResult.model_validate(result)

        return {
            "match_result": result.model_dump(),
            "task_status": "analyzing",
            "error": "",
        }

    except Exception as exc:
        return {
            "task_status": "failed",
            "error": (
                f"岗位匹配分析失败："
                f"{type(exc).__name__}: {exc}"
            ),
        }

# 得到优化计划
def plan_node(
    state: AgentState,
) -> dict:
    """
    根据岗位匹配结果制定简历优化计划。

    读取：
        resume_profile
        job_profile
        match_result

    写入：
        optimization_plan
        task_status
    """
    try:
        resume_profile = ResumeProfile.model_validate(
            state["resume_profile"]
        )

        job_profile = JobProfile.model_validate(
            state["job_profile"]
        )

        match_result = MatchResult.model_validate(
            state["match_result"]
        )

        plan = optimizer.create_plan(
            resume_profile=resume_profile,
            job_profile=job_profile,
            match_result=match_result,
            rag_context=state.get("rag_context", ""),
        )

        if not isinstance(plan, OptimizationPlan):
            plan = OptimizationPlan.model_validate(plan)

        return {
            "optimization_plan": plan.model_dump(),
            "task_status": "awaiting_approval",
            "error": "",
        }

    except Exception as exc:
        return {
            "task_status": "failed",
            "error": (
                f"优化计划生成失败："
                f"{type(exc).__name__}: {exc}"
            ),
        }


def plan_approval_node(
    state: AgentState,
) -> dict:
    """
    暂停工作流并等待用户确认简历优化计划。

    读取：
        optimization_plan

    写入：
        plan_approved
    """
    decision = interrupt(
        {
            "type": "resume_plan_approval",
            "message": "请确认是否执行以下简历优化计划。",
            "plan": state["optimization_plan"],
        }
    )

    # 推荐外部 resume 时传入：
    # {"approved": True}
    # 或：
    # {"approved": False}

    if isinstance(decision, dict):
        approved = bool(
            decision.get("approved", False)
        )
    else:
        approved = bool(decision)

    return {
        "plan_approved": approved,
    }

def rewrite_node(
    state: AgentState,
) -> dict:
    """
    根据优化计划生成候选简历。

    如果当前任务处于修复循环中，则同时根据
    repair_instructions 对上一版候选简历进行定向修复。

    读取：
        resume_profile
        job_profile
        optimization_plan
        optimized_resume（可选）
        repair_instructions（可选）
        target_language（可选）

    写入：
        optimized_resume
        changes
        task_status
    """
    try:
        resume_profile = ResumeProfile.model_validate(
            state["resume_profile"]
        )

        job_profile = JobProfile.model_validate(
            state["job_profile"]
        )

        plan = OptimizationPlan.model_validate(
            state["optimization_plan"]
        )

        result = optimizer.rewrite(
            resume_profile=resume_profile,
            job_profile=job_profile,
            plan=plan,
            previous_resume=state.get(
                "optimized_resume"
            ),
            repair_instructions=state.get(
                "repair_instructions", []
            ),
            target_language=state.get(
                "target_language", "auto"
            ),
        )

        if not isinstance(result, RewriteResult):
            result = RewriteResult.model_validate(result)

        return {
            "optimized_resume": result.content,
            "changes": [
                change.model_dump()
                for change in result.changes
            ],
            "task_status": "rewriting",
            "error": "",
        }

    except Exception as exc:
        return {
            "task_status": "failed",
            "error": (
                f"简历改写失败："
                f"{type(exc).__name__}: {exc}"
            ),
        }

def validate_node(
    state: AgentState,
) -> dict:
    """
    校验候选简历的事实一致性、岗位关键词覆盖、
    格式以及整体内容质量。

    原始简历文本始终作为事实校验的 Ground Truth。

    读取：
        resume_input
        optimized_resume
        job_profile

    写入：
        validation_results
        task_status
    """
    try:
        resume_input = ResumeInput.model_validate(
            state["resume_input"]
        )

        job_profile = JobProfile.model_validate(
            state["job_profile"]
        )

        results = validator.validate(
            original_resume=resume_input.content,
            optimized_resume=state["optimized_resume"],
            job_profile=job_profile,
        )

        validated_results = [
            (
                item
                if isinstance(item, ValidationResult)
                else ValidationResult.model_validate(item)
            )
            for item in results
        ]

        return {
            "validation_results": [
                item.model_dump()
                for item in validated_results
            ],
            "task_status": "validating",
            "error": "",
        }

    except Exception as exc:
        return {
            "task_status": "failed",
            "error": (
                f"简历校验失败："
                f"{type(exc).__name__}: {exc}"
            ),
        }

def repair_node(
    state: AgentState,
) -> dict:
    """
    根据上一轮校验失败结果生成定向修复要求。

    本节点只制定修复要求，不直接修改候选简历。

    读取：
        validation_results
        optimized_resume

    写入：
        repair_instructions
        repair_attempts
    """
    print("repair")
    try:
        failed_results = [
            ValidationResult.model_validate(item)
            for item in state.get(
                "validation_results", []
            )
            if not item.get("passed", False)
        ]

        instructions = repair_service.build_instructions(
            optimized_resume=state[
                "optimized_resume"
            ],
            validation_results=failed_results,
        )

        return {
            "repair_instructions": instructions,
            "repair_attempts": (
                state.get("repair_attempts", 0) + 1
            ),
        }

    except Exception as exc:
        return {
            "task_status": "failed",
            "error": (
                f"简历修复计划生成失败："
                f"{type(exc).__name__}: {exc}"
            ),
        }

def blocked_node(
    state: AgentState,
) -> dict:
    """
    当任务无法或不应继续自动执行时，
    将任务标记为 blocked 并生成阻塞原因。

    blocked 属于业务层正常停止，
    不等同于程序执行异常 failed。
    """
    print("blocked")
    if state.get("plan_approved") is False:
        reason = "用户未批准简历优化计划。"

    else:
        failed_results = [
            ValidationResult.model_validate(item)
            for item in state.get(
                "validation_results", []
            )
            if not item.get("passed", False)
        ]

        if failed_results:
            reasons = [
                result.message
                for result in failed_results
            ]

            reason = (
                "候选简历存在无法继续自动修复的问题："
                + "；".join(reasons)
            )

        else:
            reason = (
                state.get("error")
                or "任务无法继续自动执行。"
            )

    return {
        "task_status": "blocked",
        "error": reason,
    }

def finalize_node(
    state: AgentState,
) -> dict:
    """
    汇总整个简历优化流程，生成最终结构化结果。

    completed:
        简历优化并通过校验。

    blocked:
        因用户拒绝或存在无法安全自动修复的问题而停止。

    failed:
        因系统执行异常而失败。
    """
    print("final")
    current_status = state.get(
        "task_status",
        "failed",
    )

    if current_status == "blocked":
        final_status = "blocked"

    elif current_status == "failed":
        final_status = "failed"

    else:
        final_status = "completed"

    match_result = None

    if state.get("match_result"):
        match_result = MatchResult.model_validate(
            state["match_result"]
        )

    changes = [
        ResumeChange.model_validate(item)
        for item in state.get("changes", [])
    ]

    validation_results = [
        ValidationResult.model_validate(item)
        for item in state.get(
            "validation_results", []
        )
    ]

    result = ResumeOptimizationResult(
        status=final_status,
        optimized_resume=state.get(
            "optimized_resume"
        ),
        match_result=match_result,
        changes=changes,
        validation_results=validation_results,
        error=state.get("error") or None,
    )

    return {
        "final_answer": result.model_dump(),
        "task_status": final_status,
    }
