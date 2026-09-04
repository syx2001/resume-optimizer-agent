# app/tools/tools.py
from app.tools.knowledge_base import search_knowledge_base
from app.tools.repository import REPOSITORY_READ_TOOLS
from langchain_core.tools import tool
from datetime import datetime
from typing import Literal
from app.tools.resume_tools import RESUME_TOOLS
# from mesh_tools import MESH_TOOLS
@tool
def calculator(a: float, b: float, operation: Literal[
        "add",
        "subtract",
        "multiply",
        "divide",
    ],) -> float:
    """Perform a mathematical operation on two numbers."""

    if operation == "add":
        return a + b
    elif operation == "subtract":
        return a - b
    elif operation == "multiply":
        return a * b
    elif operation == "divide":
        if b == 0:
            raise ValueError("Cannot divide by zero.")
        return a / b

    raise ValueError(f"Unsupported operation: {operation}")


@tool
def get_current_time() -> str:
    """Get the current local system time."""

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")



tools = [
    calculator,
    get_current_time,
    search_knowledge_base,
    *REPOSITORY_READ_TOOLS,
    *RESUME_TOOLS,
]
