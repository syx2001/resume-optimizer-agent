# app/core/config.py

import os

from dotenv import load_dotenv


load_dotenv()


class Settings:
    # =========================
    # Database
    # =========================
    POSTGRES_URI: str = os.getenv(
        "POSTGRES_URI",
        "",
    )

    # =========================
    # LLM
    # =========================
    LLM_MODEL: str = os.getenv(
        "LLM_MODEL",
        "deepseek-v4-flash",
    )

    LLM_API_KEY: str = os.getenv(
        "LLM_API_KEY",
        "",
    )

    DEEPSEEK_API_KEY: str = os.getenv(
        "DEEPSEEK_API_KEY",
        "",
    )

    DEEPSEEK_BASE_URL: str = os.getenv(
        "DEEPSEEK_BASE_URL",
        "",
    )

    # =========================
    # Embedding
    # =========================
    EMBEDDING_MODEL: str = os.getenv(
        "EMBEDDING_MODEL",
        "qwen3.7-text-embedding",
    )

    QWEN_API_KEY: str = os.getenv(
        "QWEN_API_KEY",
        "",
    )

    QWEN_BASE_URL: str = os.getenv(
        "QWEN_BASE_URL",
        "",
    )

    EMBEDDING_DIMS: int = int(
        os.getenv(
            "EMBEDDING_DIMS",
            "1024",
        )
    )

    # =========================
    # RAG
    # =========================
    RAG_TOP_K: int = int(
        os.getenv(
            "RAG_TOP_K",
            "5",
        )
    )

    RAG_SCORE_THRESHOLD: float = float(
        os.getenv(
            "RAG_SCORE_THRESHOLD",
            "0.7",
        )
    )

    SEMANTIC_MATCH_THRESHOLD: float = float(
        os.getenv(
            "SEMANTIC_MATCH_THRESHOLD",
            "0.55",
        )
    )

    # =========================
    # Tool Execution
    # =========================
    TOOL_TIMEOUT_SECONDS: int = int(
        os.getenv(
            "TOOL_TIMEOUT_SECONDS",
            "30",
        )
    )

    TOOL_MAX_RETRIES: int = int(
        os.getenv(
            "TOOL_MAX_RETRIES",
            "2",
        )
    )
    
    MEMORY_TOP_K: int = int(
    os.getenv(
        "MEMORY_TOP_K",
        "5",
    )
    )

    MEMORY_SCORE_THRESHOLD: float = float(
        os.getenv(
            "MEMORY_SCORE_THRESHOLD",
            "0.7",
        )
    )


settings = Settings()
