from langchain_openai import OpenAIEmbeddings
from app.core.config import settings


embedding_model = OpenAIEmbeddings(
    model=settings.EMBEDDING_MODEL,
    api_key=settings.QWEN_API_KEY,
    base_url=settings.QWEN_BASE_URL,
    check_embedding_ctx_length=False
)
