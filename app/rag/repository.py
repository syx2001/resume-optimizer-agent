from langgraph.store.base import BaseStore

from app.rag.models import ChunkSearchResult, DocumentChunk, DocumentMeta


class RAGRepository:
    def __init__(self, store: BaseStore):
        self.store = store

    def _chunk_namespace(self) -> tuple[str, ...]:
        return ("rag", "chunks")

    def _document_namespace(self) -> tuple[str, ...]:
        return ("rag", "documents")

    def get_document(self, document_id: str) -> DocumentMeta | None:
        item = self.store.get(self._document_namespace(), document_id)
        if item is None:
            return None
        return DocumentMeta.model_validate(item.value)

    def put_document(self, document: DocumentMeta) -> None:
        self.store.put(
            self._document_namespace(),
            document.document_id,
            document.model_dump(mode="json"),
            index=False,
        )

    def put_chunk(self, chunk: DocumentChunk) -> None:
        self.store.put(
            self._chunk_namespace(),
            chunk.chunk_id,
            chunk.model_dump(mode="json"),
        )

    def search(self, query: str, limit: int = 5) -> list[ChunkSearchResult]:
        items = self.store.search(
            self._chunk_namespace(),
            query=query,
            limit=limit,
        )
        return [
            ChunkSearchResult(
                chunk=DocumentChunk.model_validate(item.value),
                score=item.score,
            )
            for item in items
            if item.score is not None
        ]

    def delete_document_chunks(self, document_id: str) -> None:
        items = self.store.search(
            self._chunk_namespace(),
            filter={"document_id": document_id},
            limit=1000,
        )
        for item in items:
            self.store.delete(self._chunk_namespace(), item.key)

    def delete_document(self, document_id: str) -> bool:
        document = self.get_document(document_id)
        if document is None:
            return False

        self.delete_document_chunks(document_id)
        self.store.delete(self._document_namespace(), document_id)
        return True
