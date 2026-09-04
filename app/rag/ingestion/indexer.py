from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from app.rag.ingestion.loader import (
    load_pdf,
    load_text_file,
)
from app.rag.ingestion.splitter import (
    split_pages,
    split_text,
)
from app.rag.models import (
    DocumentChunk,
    DocumentMeta,
)
from app.rag.repository import RAGRepository


def make_document_id(file_path: str) -> str:
    path = Path(file_path).resolve()

    return sha256(
        str(path).encode("utf-8")
    ).hexdigest()[:16]


def make_content_hash(text: str) -> str:
    return sha256(
        text.encode("utf-8")
    ).hexdigest()


def ingest_file(
    file_path: str,
    repository: RAGRepository,
) -> int:

    path = Path(file_path)
    suffix = path.suffix.lower()

    source = path.name
    document_id = make_document_id(file_path)

    # =========================
    # Load + Split
    # =========================

    if suffix == ".pdf":
        pages = load_pdf(file_path)

        full_text = "\n".join(
            page["content"]
            for page in pages
        )

        chunks = split_pages(pages)

    elif suffix in {".md", ".txt"}:
        full_text = load_text_file(file_path)

        chunks = [
            {
                "page_number": None,
                "content": content,
            }
            for content in split_text(full_text)
        ]

    else:
        raise ValueError(
            f"Unsupported file type: {suffix}"
        )

    # =========================
    # Incremental Indexing
    # =========================

    content_hash = make_content_hash(full_text)

    old_document = repository.get_document(
        document_id
    )

    # 文件存在，而且内容没变化
    if (
        old_document
        and old_document.content_hash == content_hash
    ):
        print(
            f"[SKIP] {source} has not changed."
        )
        return 0

    # 文件存在，但是内容发生变化
    if old_document:
        repository.delete_document(
            document_id
        )

    # =========================
    # Store Chunks
    # =========================

    for index, chunk_data in enumerate(chunks):

        chunk = DocumentChunk(
            document_id=document_id,
            chunk_id=f"{document_id}:{index}",
            chunk_index=index,
            source=source,
            page_number=chunk_data["page_number"],
            content=chunk_data["content"],
        )

        repository.put_chunk(chunk)

    # =========================
    # Store Document Metadata
    # =========================

    now = datetime.now(timezone.utc)

    document = DocumentMeta(
        document_id=document_id,
        source=source,
        content_hash=content_hash,
        created_at=(
            old_document.created_at
            if old_document
            else now
        ),
        updated_at=now,
    )

    repository.put_document(document)

    print(
        f"[INDEXED] {source}: {len(chunks)} chunks"
    )

    return len(chunks)