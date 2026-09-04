"""简历解析服务。"""

from langchain_core.messages import HumanMessage, SystemMessage

from app.infrastructure.ai.llm import deepseek_v4_pro
from app.schemas import ResumeProfile
from app.agent.prompts import RESUME_PARSE_SYSTEM_PROMPT
from app.infrastructure.ai.structured import invoke_structured
test_tools = [{
    "type": "function",
    "function": {
        "name": "test",
        "parameters": {"type": "object", "properties": {"a": {"type": "string"}}}
    }
}]

class ResumeParser:
    """
    使用大语言模型将原始简历文本解析为结构化 ResumeProfile。

    本 Service 只负责简历语义解析，不负责：
    1. LangGraph State 的读取和更新；
    2. Workflow 路由；
    3. PDF / DOCX 文件读取；
    4. 岗位匹配；
    5. 简历改写。
    """

    def __init__(self) -> None:
        """
        初始化简历解析服务。
        """
        # 使用项目统一配置的 DeepSeek 模型，
        # 并要求模型按照 ResumeProfile 返回结构化结果。
        self.structured_llm = (
            deepseek_v4_pro.with_structured_output(
                ResumeProfile,
                method="function_calling",
            )
        )

    def parse(
        self,
        content: str,
        language: str = "auto",
    ) -> ResumeProfile:
        """
        将原始简历文本解析为 ResumeProfile。

        Args:
            content:
                原始简历文本。

            language:
                原始简历语言，例如 zh、en、auto。

        Returns:
            ResumeProfile:
                结构化简历信息。

        Raises:
            ValueError:
                当简历内容为空时抛出。
        """

        content = content.strip()

        if not content:
            raise ValueError("简历内容不能为空。")

        messages = [
            SystemMessage(
                content=RESUME_PARSE_SYSTEM_PROMPT
            ),
            HumanMessage(
                content=(
                    f"简历语言：{language}\n\n"
                    "请解析以下简历内容：\n\n"
                    f"{content}"
                )
            ),
        ]
        result = invoke_structured(self.structured_llm, messages, ResumeProfile)
        return result
