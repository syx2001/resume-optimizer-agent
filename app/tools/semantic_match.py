"""Semantic resume-to-job matching powered by the configured Qwen embeddings."""

import math
import re

from langchain_core.tools import tool

from app.core.config import settings
from app.infrastructure.ai.embedding import embedding_model


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def _embed_in_batches(texts: list[str], batch_size: int = 20) -> list[list[float]]:
    """Embed texts without exceeding the provider's maximum batch size."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        vectors.extend(embedding_model.embed_documents(texts[start:start + batch_size]))
    return vectors


def _split_evidence_units(text: str) -> list[str]:
    """Split a resume into small evidence units instead of large paragraphs."""
    units = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = re.split(r"(?<=[。！？.!?])\s+", line)
        units.extend(part.strip() for part in parts if part.strip())
    return units or [text]


@tool
def semantic_match(resume_text: str, requirements: list[str]) -> dict:
    """Compare resume evidence with job requirements using Qwen Embeddings.

    It compares each requirement with resume chunks using embedding cosine
    similarity. It is read-only and does not invent skills or rewrite the
    resume. Similarity is evidence of related wording, not proof that a
    candidate has the skill.
    """
    resume_text = (resume_text or "").strip()
    requirements = [item.strip() for item in requirements if item and item.strip()]
    if not resume_text or not requirements:
        return {"score": 0.0 if requirements else 1.0, "matched": [], "missing": requirements, "details": [], "threshold": settings.SEMANTIC_MATCH_THRESHOLD}

    chunks = _split_evidence_units(resume_text)
    vectors = _embed_in_batches([*chunks, *requirements])
    chunk_vectors = vectors[:len(chunks)]
    requirement_vectors = vectors[len(chunks):]
    details = []

    for requirement, requirement_vector in zip(requirements, requirement_vectors):
        scores = [_cosine_similarity(requirement_vector, chunk_vector) for chunk_vector in chunk_vectors]
        best_index = max(range(len(scores)), key=scores.__getitem__)
        best_score, evidence, method = scores[best_index], chunks[best_index], "semantic"
        matched = best_score >= settings.SEMANTIC_MATCH_THRESHOLD
        evidence_preview = " ".join(evidence.split())[:240]
        print(
            f"[SEMANTIC MATCH] requirement={requirement!r} "
            f"score={best_score:.4f} threshold={settings.SEMANTIC_MATCH_THRESHOLD:.4f} "
            f"matched={matched} method={method} evidence={evidence_preview!r}",
            flush=True,
        )
        details.append({
            "requirement": requirement,
            "matched": matched,
            "score": round(best_score, 4),
            "method": method,
            "evidence": evidence[:500],
        })

    matched = [item["requirement"] for item in details if item["matched"]]
    missing = [item["requirement"] for item in details if not item["matched"]]
    return {"score": round(len(matched) / len(requirements), 2), "matched": matched, "missing": missing, "details": details, "threshold": settings.SEMANTIC_MATCH_THRESHOLD}


SEMANTIC_MATCH_TOOLS = [semantic_match]
