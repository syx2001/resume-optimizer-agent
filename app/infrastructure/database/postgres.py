"""Lazy PostgreSQL resources for LangGraph checkpointing and Store."""

from dataclasses import dataclass
from functools import lru_cache

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore

from app.core.config import settings
from app.infrastructure.ai.embedding import embedding_model


@dataclass
class DatabaseResources:
    checkpointer: PostgresSaver
    store: PostgresStore
    checkpointer_context: object
    store_context: object

    def close(self) -> None:
        self.store_context.__exit__(None, None, None)
        self.checkpointer_context.__exit__(None, None, None)


@lru_cache(maxsize=1)
def get_database_resources() -> DatabaseResources:
    """Open resources on first use; importing this module has no DB side effect."""
    if not settings.POSTGRES_URI:
        raise RuntimeError("POSTGRES_URI is required to initialize the database")

    checkpointer_context = PostgresSaver.from_conn_string(settings.POSTGRES_URI)
    store_context = PostgresStore.from_conn_string(
        settings.POSTGRES_URI,
        index={"dims": settings.EMBEDDING_DIMS, "embed": embedding_model},
    )
    checkpointer = checkpointer_context.__enter__()
    store = store_context.__enter__()
    return DatabaseResources(checkpointer, store, checkpointer_context, store_context)


def initialize_database() -> DatabaseResources:
    resources = get_database_resources()
    resources.checkpointer.setup()
    resources.store.setup()
    return resources


def close_database() -> None:
    if get_database_resources.cache_info().currsize:
        resources = get_database_resources()
        resources.close()
        get_database_resources.cache_clear()
