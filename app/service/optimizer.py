"""简历优化服务。"""

import json

from langchain_core.messages import HumanMessage, SystemMessage

from app.infrastructure.ai.llm import deepseek_v4_pro
from app.schemas import (
    JobProfile,
    MatchResult,
    OptimizationPlan,
    ResumeProfile,
    RewriteResult,
)
from app.agent.prompts import (
    OPTIMIZATION_PLAN_SYSTEM_PROMPT,
    RESUME_REWRITE_SYSTEM_PROMPT,
)
from app.infrastructure.ai.structured import invoke_structured


class ResumeOptimizer:
    """
    使用大语言模型完成简历优化计划制定与简历改写。

    本 Service 负责：
    1. 根据 ResumeProfile、JobProfile、MatchResult 制定优化计划；
    2. 根据优化计划生成候选简历；
    3. 在修复循环中根据 repair_instructions 定向修改候选简历。

    本 Service 不负责：
    1. LangGraph State 管理；
    2. Workflow 路由；
    3. 用户审批；
    4. 最终事实校验；
    5. 文件导出。
    """

    def __init__(self) -> None:
        """
        初始化简历优化服务。
        """

        self.plan_llm = (
            deepseek_v4_pro.with_structured_output(
                OptimizationPlan,
                method="function_calling",
            )
        )

        self.rewrite_llm = (
            deepseek_v4_pro.with_structured_output(
                RewriteResult,
                method="function_calling",
            )
        )

    def create_plan(
        self,
        resume_profile: ResumeProfile,
        job_profile: JobProfile,
        match_result: MatchResult,
        rag_context: str = "",
    ) -> OptimizationPlan:
        """
        根据候选人简历、岗位要求和匹配结果生成优化计划。

        Args:
            resume_profile:
                结构化候选人简历。

            job_profile:
                结构化目标岗位信息。

            match_result:
                当前简历与岗位之间的匹配分析结果。

        Returns:
            OptimizationPlan:
                简历优化目标和执行步骤。
        """

        resume_json = json.dumps(#pydantic -> dict
            resume_profile.model_dump(),
            ensure_ascii=False,
            indent=2,
        )

        job_json = json.dumps(
            job_profile.model_dump(),
            ensure_ascii=False,
            indent=2,
        )

        match_json = json.dumps(
            match_result.model_dump(),
            ensure_ascii=False,
            indent=2,
        )

        rag_context = rag_context or "暂无可用的外部简历优化规范。"

        messages = [
            SystemMessage(
                content=OPTIMIZATION_PLAN_SYSTEM_PROMPT
            ),
            HumanMessage(
                content=(
                    "请根据以下候选人简历、目标岗位和匹配结果，"
                    "制定简历优化计划。\n\n"
                    "【候选人简历信息】\n"
                    f"{resume_json}\n\n"
                    "【目标岗位信息】\n"
                    f"{job_json}\n\n"
                    "【岗位匹配结果】\n"
                    f"{match_json}\n\n"
                    "【外部简历优化规范】\n"
                    f"{rag_context}"
                )
            ),
        ]

        return invoke_structured(self.plan_llm, messages, OptimizationPlan)

    def rewrite(
        self,
        resume_profile: ResumeProfile,
        job_profile: JobProfile,
        plan: OptimizationPlan,
        *,
        previous_resume: str | None = None,
        repair_instructions: list[str] | None = None,
        target_language: str = "auto",
    ) -> RewriteResult:
        """
        根据优化计划生成或修复候选简历。

        第一次执行时：
            previous_resume 通常为空，
            根据原始 ResumeProfile 生成优化后的候选简历。

        修复循环时：
            previous_resume 为上一版候选简历，
            repair_instructions 为校验阶段生成的修复要求。

        Args:
            resume_profile:
                原始简历解析结果。
                始终作为事实边界。

            job_profile:
                目标岗位结构化信息。

            plan:
                用户已批准的优化计划。

            previous_resume:
                上一版候选简历。
                第一次改写时可以为空。

            repair_instructions:
                校验失败后生成的定向修复指令。

            target_language:
                目标输出语言。

        Returns:
            RewriteResult:
                新的候选简历以及本轮修改记录。
        """

        repairs = repair_instructions or []

        resume_json = json.dumps(
            resume_profile.model_dump(),
            ensure_ascii=False,
            indent=2,
        )

        job_json = json.dumps(
            job_profile.model_dump(),
            ensure_ascii=False,
            indent=2,
        )

        plan_json = json.dumps(
            plan.model_dump(),
            ensure_ascii=False,
            indent=2,
        )

        previous_resume_text = (
            previous_resume.strip()
            if previous_resume
            else "无。这是第一次优化。"
        )

        repair_text = (
            "\n".join(
                f"- {instruction}"
                for instruction in repairs
            )
            if repairs
            else "无额外修复要求。"
        )

        messages = [
            SystemMessage(
                content=RESUME_REWRITE_SYSTEM_PROMPT
            ),
            HumanMessage(
                content=(
                    f"目标输出语言：{target_language}\n\n"
                    "【原始简历事实信息】\n"
                    f"{resume_json}\n\n"
                    "【目标岗位信息】\n"
                    f"{job_json}\n\n"
                    "【已批准的优化计划】\n"
                    f"{plan_json}\n\n"
                    "【上一版候选简历】\n"
                    f"{previous_resume_text}\n\n"
                    "【本轮修复要求】\n"
                    f"{repair_text}\n\n"
                    "请生成新的候选简历。"
                )
            ),
        ]

        return invoke_structured(self.rewrite_llm, messages, RewriteResult)
