"""职位描述解析服务。"""

from langchain_core.messages import HumanMessage, SystemMessage

from app.infrastructure.ai.llm import deepseek_v4_flash
from app.schemas import JobProfile
from app.agent.prompts import JOB_PARSE_SYSTEM_PROMPT
from app.infrastructure.ai.structured import invoke_structured


class JobParser:
    """
    使用大语言模型将原始职位描述解析为结构化 JobProfile。

    本 Service 只负责职位描述的语义解析，不负责：
    1. LangGraph State 的读取和更新；
    2. Workflow 路由；
    3. 简历匹配；
    4. 简历优化；
    5. 简历内容改写。
    """

    def __init__(self) -> None:
        """
        初始化职位描述解析服务。
        """

        # 使用项目统一配置的 DeepSeek 模型，
        # 并要求模型按照 JobProfile 返回结构化结果。
        self.structured_llm = (
            deepseek_v4_flash.with_structured_output(
                JobProfile,
                method="function_calling",
            )
        )

    def parse(
        self,
        content: str,
        role_title: str | None = None,
    ) -> JobProfile:
        """
        将原始职位描述解析为 JobProfile。

        Args:
            content:
                原始职位描述文本。

            role_title:
                可选的目标职位名称。
                如果用户已经明确提供职位名称，可以帮助模型理解岗位上下文。

        Returns:
            JobProfile:
                结构化岗位信息。

        Raises:
            ValueError:
                当职位描述内容为空时抛出。
        """

        content = content.strip()

        if not content:
            raise ValueError("职位描述内容不能为空。")

        role_title_text = (
            role_title.strip()
            if role_title and role_title.strip()
            else "未提供"
        )

        messages = [
            SystemMessage(
                content=JOB_PARSE_SYSTEM_PROMPT
            ),
            HumanMessage(
                content=(
                    f"目标职位名称：{role_title_text}\n\n"
                    "请解析以下职位描述：\n\n"
                    f"{content}"
                )
            ),
        ]

        result = invoke_structured(self.structured_llm, messages, JobProfile)

        return result
