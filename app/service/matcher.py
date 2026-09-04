"""简历与岗位匹配分析服务。"""

import json
from collections.abc import Callable

from langchain_core.messages import HumanMessage, SystemMessage,ToolMessage
from pydantic import BaseModel
from app.infrastructure.ai.llm import deepseek_v4_flash
from app.schemas import (
    JobProfile,
    MatchResult,
    ResumeProfile,
)
from app.agent.prompts import MATCH_SYSTEM_PROMPT
from app.tools.semantic_match import SEMANTIC_MATCH_TOOLS
from app.infrastructure.ai.structured import invoke_structured

class ResumeJobMatcher:
    """
    使用大语言模型分析 ResumeProfile 与 JobProfile 的匹配程度。

    本 Service 负责：
    1. 判断候选人已有能力与岗位要求之间的语义匹配关系；
    2. 识别已经满足的要求；
    3. 识别缺失或缺乏证据支持的岗位要求；
    4. 给出整体岗位匹配分数。

    本 Service 不负责：
    1. 修改简历；
    2. 虚构候选人能力；
    3. 制定优化计划；
    4. LangGraph Workflow 路由。
    """
    MAX_TOOL_ITERATIONS = 1
    def __init__(self) -> None:
        """初始化岗位匹配分析服务。"""

        self.tool_llm = deepseek_v4_flash.bind_tools(SEMANTIC_MATCH_TOOLS)

        self.final_llm = (
            deepseek_v4_flash.with_structured_output(
                MatchResult,
                method="function_calling",
            )
        )
        self.tools_by_name = {tool.name: tool for tool in SEMANTIC_MATCH_TOOLS}

    def match(
        self,
        resume_profile: ResumeProfile,
        job_profile: JobProfile,
        rag_context: str = "",
        event_callback: Callable[[dict], None] | None = None,
    ) -> MatchResult:
        """
        分析简历与目标岗位之间的匹配程度。

        Args:
            resume_profile:
                从原始简历解析得到的结构化候选人信息。

            job_profile:
                从职位描述解析得到的结构化岗位信息。

        Returns:
            MatchResult:
                包含整体匹配分数、已匹配要求和缺失要求。
        """

        resume_json = resume_profile.model_dump_json(indent=2)
        job_json = job_profile.model_dump_json(indent=2)

        messages = [
            SystemMessage(
                content=MATCH_SYSTEM_PROMPT+"你可以根据分析需要自主决定是否调用工具。"
                    "工具结果只能作为辅助证据，"
                    "最终结论必须结合简历经历和岗位要求综合判断。"
            ),
            SystemMessage(
                content=(
                    "Match阶段工具使用规则：岗位与简历匹配时，如需工具辅助，"
                    "可以调用用于匹配岗位与简历的工具，用于比较简历文本与岗位关键词的覆盖情况。"
                    "工具调用完成后停止调用工具，并生成最终的 MatchResult。"
                )
            ),
            SystemMessage(
                content=(
                    "Match 阶段需要比较岗位要求与候选人简历时，使用 semantic_match 工具。"
                    "该工具基于 Qwen Embedding，先做字面匹配，再做语义相似度匹配，返回匹配项、缺失项和证据片段。"
                    "工具只读，不改写简历；RAG 已由前置节点完成。请根据工具返回的 Observation 自主判断是否还需要继续调用工具；"
                    "如果信息已经足够，请停止调用工具并生成 MatchResult。不要重复发起完全相同的工具调用。"
                )
            ),
            HumanMessage(
                content=(
                    "请分析下面候选人简历与目标岗位之间的匹配情况。\n\n"
                    "【候选人简历信息】\n"
                    f"{resume_json}\n\n"
                    "【目标岗位信息】\n"
                    f"{job_json}\n\n"
                    "【外部简历优化规范】\n"
                    f"{rag_context or '暂无可用的外部简历优化规范。'}"
                )
            ),
        ]
        for iteration in range(1, self.MAX_TOOL_ITERATIONS + 1):
            ai_message = self.tool_llm.invoke(messages)

            messages.append(ai_message)

            if not ai_message.tool_calls:
                break

            for tool_call in ai_message.tool_calls:
                tool_name = tool_call["name"]
                print(
                    f"[MATCH TOOL] iteration={iteration} name={tool_name}",
                    flush=True,
                )

                if event_callback:
                    event_callback({
                        "kind": "match_tool_call",
                        "tool": tool_name,
                        "status": "started",
                    })

                tool = self.tools_by_name.get(tool_name)

                if tool is None:
                    raise ValueError(
                        f"LLM 请求了未知工具：{tool_name}"
                    )

                try:
                    tool_result = tool.invoke(tool_call["args"])
                except Exception as exc:
                    print(
                        f"[MATCH TOOL ERROR] iteration={iteration} name={tool_name} "
                        f"error={type(exc).__name__}: {exc}",
                        flush=True,
                    )
                    raise

                print(
                    f"[MATCH TOOL DONE] iteration={iteration} name={tool_name}",
                    flush=True,
                )

                if event_callback:
                    event_callback({
                        "kind": "match_tool_call",
                        "tool": tool_name,
                        "status": "completed",
                    })

                if isinstance(tool_result, BaseModel):
                    tool_content = tool_result.model_dump_json()
                elif isinstance(tool_result, str):
                    tool_content = tool_result
                else:
                    tool_content = json.dumps(
                        tool_result,
                        ensure_ascii=False,
                    )

                messages.append(
                    ToolMessage(
                        content=tool_content,
                        tool_call_id=tool_call["id"],
                    )
                )

            # Match performs one complete semantic comparison. The iterative
            # ReAct-style loop belongs to the later validate/repair/rewrite
            # workflow, not to this one-shot matching step.
            if any(call["name"] == "semantic_match" for call in ai_message.tool_calls):
                break

        else:
            raise RuntimeError(
                "岗位匹配工具调用超过最大迭代次数。"
            )

        messages.append(
            HumanMessage(
                content=(
                    "工具调用阶段已经结束。"
                    "请综合候选人简历、岗位要求以及工具返回的证据，"
                    "生成最终岗位匹配结果。"
                )
            )
        )
        return invoke_structured(self.final_llm, messages, MatchResult)

