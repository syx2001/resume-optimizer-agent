from langchain_openai import ChatOpenAI
from app.core.config import settings

#deepseek
deepseek_v4_flash=ChatOpenAI(
    model=settings.LLM_MODEL,
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_BASE_URL,
    extra_body={"thinking": {"type": "disabled"}}
)
deepseek_v4_pro=ChatOpenAI(
    model="deepseek-v4-pro",
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_BASE_URL,
    extra_body={"thinking": {"type": "disabled"}}
)
deepseek_v4_flash_vision=ChatOpenAI(
    model="deepseek-v4-flash-vision-exp",
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_BASE_URL,
    extra_body={"thinking": {"type": "disabled"}}
)
