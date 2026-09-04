from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.infrastructure.database.postgres import (
    initialize_database,
    close_database,
)
from app.rag.repository import RAGRepository
from app.rag.ingestion.indexer import ingest_file


resources = initialize_database()

try:
    repository = RAGRepository(resources.store)

    count = ingest_file(
        str(PROJECT_ROOT / "knowledge_base" / "resume_agent_guidelines.txt"),
        repository,
    )

    print(f"Indexed chunks: {count}")
finally:
    close_database()
