"""Compatibility helpers for providers without structured-output support."""

import json
from typing import TypeVar

from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.infrastructure.ai.llm import deepseek_v4_pro


ModelT = TypeVar("ModelT", bound=BaseModel)


def invoke_structured(
    structured_llm,
    messages: list,
    schema: type[ModelT],
) -> ModelT:
    """Use tool-based structured output, with plain-JSON fallback."""

    structured_error = None
    try:
        result = structured_llm.invoke(messages)
        if isinstance(result, schema):
            return result
        return schema.model_validate(result)
    except Exception as exc:
        # OpenAI-compatible providers may return None, an empty object, or
        # invalid tool arguments without raising a response_format error.
        structured_error = exc

    schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    fallback_messages = [
        *messages,
        HumanMessage(
            content=(
                "请只返回一个合法 JSON 对象，不要返回 Markdown、解释文字或代码块。"
                f"JSON 必须符合以下 schema：{schema_json}"
            )
        ),
    ]
    response = deepseek_v4_pro.invoke(fallback_messages)
    content = response.content if hasattr(response, "content") else response

    if not isinstance(content, str):
        raise ValueError("模型返回的结构化结果不是文本 JSON")

    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`").strip()
        if content.lower().startswith("json"):
            content = content[4:].strip()

    try:
        return schema.model_validate(json.loads(content))
    except (json.JSONDecodeError, ValueError) as parse_error:
        raise ValueError(
            f"无法将模型返回内容解析为 {schema.__name__}: {content[:1000]}"
        ) from parse_error
