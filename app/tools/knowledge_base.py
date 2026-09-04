from langchain_core.tools import tool

from app.core.config import settings
from app.infrastructure.database.postgres import get_database_resources
from app.rag.models import RAGSearchResult, RAGSource
from app.rag.repository import RAGRepository


def _repository() -> RAGRepository:
    return RAGRepository(get_database_resources().store)


@tool
def search_knowledge_base(query: str, top_k: int | None = None) -> dict:
    """Search indexed documents; repository facts should use repository tools."""
    results = _repository().search(query=query, limit=top_k or settings.RAG_TOP_K)
    relevant_results = [
        result for result in results if result.score >= settings.RAG_SCORE_THRESHOLD
    ]
    return RAGSearchResult(
        query=query,
        sources=[
            RAGSource(
                source=result.chunk.source,
                page_number=result.chunk.page_number,
                content=result.chunk.content,
                score=result.score,
            )
            for result in relevant_results
        ],
    ).model_dump()
