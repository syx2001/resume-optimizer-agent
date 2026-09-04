"""简历校验服务。"""

import re
from typing import Iterable

from langchain_core.messages import HumanMessage, SystemMessage

from app.infrastructure.ai.llm import deepseek_v4_pro
from app.schemas import (
    JobProfile,
    ValidationResult,
)
from app.agent.prompts import FACT_VALIDATION_SYSTEM_PROMPT
from app.infrastructure.ai.structured import invoke_structured
from app.tools.semantic_match import semantic_match

class ResumeValidator:
    """
    对优化后的候选简历进行多维度校验。

    校验内容包括：
    1. 关键词覆盖检查；
    2. 基础格式检查；
    3. 基于 LLM 的事实一致性检查。

    本 Service 不负责：
    1. 修改简历；
    2. 生成修复后的简历；
    3. LangGraph State 管理；
    4. Workflow 路由。
    """

    def __init__(self) -> None:
        """
        初始化简历校验服务。
        """

        # 事实一致性检查需要 LLM 做语义判断。
        # 结果强制输出为 ValidationResult。
        self.fact_llm = (
            deepseek_v4_pro.with_structured_output(
                ValidationResult,
                method="function_calling",
            )
        )
    def validate(
        self,
        original_resume: str,
        optimized_resume: str,
        job_profile: JobProfile,
    ) -> list[ValidationResult]:
        """
        对候选简历执行完整校验。

        Args:
            original_resume:
                用户原始简历文本。
                作为事实校验的重要依据。

            optimized_resume:
                当前优化后的候选简历。

            job_profile:
                目标岗位结构化信息。

        Returns:
            list[ValidationResult]:
                所有校验结果。
        """

        original_resume = original_resume.strip()
        optimized_resume = optimized_resume.strip()

        if not original_resume:
            raise ValueError("原始简历内容不能为空。")

        if not optimized_resume:
            raise ValueError("候选简历内容不能为空。")

        results: list[ValidationResult] = []
        results.extend(
            self._semantic_keyword_advisory(
                optimized_resume=optimized_resume,
                keywords=job_profile.keywords,
            )
        )

        # 1. 关键词覆盖检查
        # Keyword semantic matching remains an advisory Match signal. It is
        # intentionally excluded from hard validation and repair decisions.

        # 2. 基础格式检查
        results.extend(
            self._validate_format(
                optimized_resume=optimized_resume,
            )
        )

        # 3. 事实一致性检查
        results.append(
            self._validate_facts(
                original_resume=original_resume,
                optimized_resume=optimized_resume,
            )
        )

        return results

    def _semantic_keyword_advisory(
        self,
        optimized_resume: str,
        keywords: Iterable[str],
    ) -> list[ValidationResult]:
        """Run semantic coverage as a non-blocking quality signal."""
        keywords = [keyword.strip() for keyword in keywords if keyword and keyword.strip()]
        if not keywords:
            return []

        print("[VALIDATION TOOL] name=semantic_match", flush=True)
        result = semantic_match.invoke({
            "resume_text": optimized_resume,
            "requirements": keywords,
        })
        print("[VALIDATION TOOL DONE] name=semantic_match", flush=True)

        matched = result.get("matched", [])
        missing = result.get("missing", [])
        message = (
            f"语义覆盖率：{len(matched)}/{len(keywords)}。"
            + (f"可能缺少：{'、'.join(missing)}。" if missing else "未发现明显缺失。")
        )
        return [
            ValidationResult(
                category="quality",
                passed=True,
                repairable=False,
                message=message,
            )
        ]

    def _validate_keywords(
        self,
        optimized_resume: str,
        keywords: Iterable[str],
    ) -> list[ValidationResult]:
        """
        检查候选简历对目标岗位关键词的覆盖情况。

        注意：
        关键词缺失并不一定意味着错误，
        因为候选人原始简历可能本身就没有该能力。

        因此这里将缺失关键词标记为可修复，
        后续 rewrite 仍需遵守事实边界，
        不能为了补关键词而虚构能力。
        """

        keywords = [
            keyword.strip()
            for keyword in keywords
            if keyword and keyword.strip()
        ]

        if not keywords:
            return [
                ValidationResult(
                    category="keyword",
                    passed=True,
                    message="目标岗位未提供需要检查的关键词。",
                    repairable=False,
                )
            ]

        print("[VALIDATION TOOL] name=semantic_match", flush=True)
        try:
            semantic_result = semantic_match.invoke({
                "resume_text": optimized_resume,
                "requirements": keywords,
            })
        except Exception as exc:
            print(
                f"[VALIDATION TOOL ERROR] name=semantic_match "
                f"error={type(exc).__name__}: {exc}",
                flush=True,
            )
            raise
        print("[VALIDATION TOOL DONE] name=semantic_match", flush=True)
        missing_keywords = semantic_result.get("missing", [])
        matched_keywords = semantic_result.get("matched", [])

        if not missing_keywords:
            return [
                ValidationResult(
                    category="keyword",
                    passed=True,
                    message="候选简历已覆盖目标岗位的主要关键词。",
                    repairable=False,
                )
            ]

        return [
            ValidationResult(
                category="keyword",
                passed=False,
                message=(
                    "候选简历未体现部分岗位关键词："
                    + "、".join(missing_keywords)
                ),
                repairable=True,
                suggestion=(
                    "检查这些关键词是否能够由原始简历中的真实经历支持；"
                    "如果能够支持，可在不改变事实的前提下强化相关表达；"
                    "如果原始简历没有证据，则不要强行添加。"
                ),
            )
        ]

    def _validate_format(
        self,
        optimized_resume: str,
    ) -> list[ValidationResult]:
        """
        执行基础格式和质量检查。

        这里只做确定性检查，不调用 LLM。
        """

        results: list[ValidationResult] = []

        # ---------- 长度检查 ----------

        if len(optimized_resume) < 100:
            results.append(
                ValidationResult(
                    category="format",
                    passed=False,
                    message="候选简历内容过短，可能缺少必要信息。",
                    repairable=True,
                    suggestion=(
                        "在不新增虚构事实的前提下，"
                        "补充原始简历中已有的重要经历和技术细节。"
                    ),
                )
            )
        else:
            results.append(
                ValidationResult(
                    category="format",
                    passed=True,
                    message="候选简历整体长度处于可接受范围。",
                    repairable=False,
                )
            )

        # ---------- 连续空行检查 ----------

        if re.search(r"\n{4,}", optimized_resume):
            results.append(
                ValidationResult(
                    category="format",
                    passed=False,
                    message="候选简历存在过多连续空行。",
                    repairable=True,
                    suggestion="压缩多余空行，保持版式紧凑。",
                )
            )
        else:
            results.append(
                ValidationResult(
                    category="format",
                    passed=True,
                    message="未发现明显的连续空行格式问题。",
                    repairable=False,
                )
            )

        return results

    def _validate_facts(
        self,
        original_resume: str,
        optimized_resume: str,
    ) -> ValidationResult:
        """
        使用 LLM 判断优化后的简历是否存在事实夸大、
        无依据补充或语义升级。
        """

        messages = [
            SystemMessage(
                content=FACT_VALIDATION_SYSTEM_PROMPT
            ),
            HumanMessage(
                content=(
                    "请检查下面优化后的候选简历是否严格建立在原始简历事实之上。\n\n"
                    "【原始简历】\n"
                    f"{original_resume}\n\n"
                    "【优化后的候选简历】\n"
                    f"{optimized_resume}"
                )
            ),
        ]

        return invoke_structured(self.fact_llm, messages, ValidationResult)
