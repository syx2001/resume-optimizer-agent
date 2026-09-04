from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

class DocumentChunk(BaseModel):
    document_id: str#避免同一个文件重复导入
    chunk_id: str
    chunk_index: int
    source: str
    content: str

    page_number: Optional[int] = None

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

class DocumentMeta(BaseModel):
    document_id: str
    source: str
    content_hash: str

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
class RAGSource(BaseModel):
    source: str
    page_number: int | None = None
    content: str
    score: float
class RAGSearchResult(BaseModel):
    query: str
    sources: list[RAGSource]
class ChunkSearchResult(BaseModel):
    chunk: DocumentChunk
    score: float