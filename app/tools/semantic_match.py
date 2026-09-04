"""使用配置的 Qwen Embedding 进行简历与岗位要求的语义匹配。"""

import math
import re

from langchain_core.tools import tool

from app.core.config import settings
from app.infrastructure.ai.embedding import embedding_model


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    """计算两个向量的余弦相似度。"""

    # 点积越大，说明两个向量的方向越接近。
    dot = sum(a * b for a, b in zip(left, right))

    # 计算两个向量的长度，用于对点积进行归一化。
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))

    # 如果任一向量是零向量，则无法计算有效的相似度。
    if not left_norm or not right_norm:
        return 0.0

    return dot / (left_norm * right_norm)


def _embed_in_batches(texts: list[str], batch_size: int = 20) -> list[list[float]]:
    """分批生成文本向量，避免超过 Embedding 服务的批量上限。"""

    vectors: list[list[float]] = []

    # 每次最多处理 batch_size 条文本，最后一批可能不足 batch_size 条。
    for start in range(0, len(texts), batch_size):
        vectors.extend(embedding_model.embed_documents(texts[start:start + batch_size]))

    return vectors


def _split_evidence_units(text: str) -> list[str]:
    """将简历拆成较小的证据单元，避免整段文本过长影响匹配精度。"""

    units = []

    # 先按换行拆分，再按中英文句号、问号和感叹号拆分。
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = re.split(r"(?<=[。！？.!?])\s+", line)
        units.extend(part.strip() for part in parts if part.strip())

    # 如果没有成功拆出内容，至少保留原始文本作为一个匹配单元。
    return units or [text]


@tool
def semantic_match(resume_text: str, requirements: list[str]) -> dict:
    """使用 Qwen Embedding 将岗位要求与简历证据进行语义匹配。

    对每条岗位要求，分别与简历中的证据单元计算余弦相似度，
    并选择相似度最高的简历片段作为最佳证据。

    该工具只读，不会虚构技能，也不会改写简历。
    相似度只能说明语义或表达相关，不能单独证明候选人确实具备该技能。
    """
    # 清理简历文本，并过滤空的岗位要求。
    resume_text = (resume_text or "").strip()
    requirements = [item.strip() for item in requirements if item and item.strip()]

    # 缺少简历时无法匹配；没有岗位要求时，视为没有缺失项。
    if not resume_text or not requirements:
        return {"score": 0.0 if requirements else 1.0, "matched": [], "missing": requirements, "details": [], "threshold": settings.SEMANTIC_MATCH_THRESHOLD}

    # 将简历拆成证据单元，并一次性为简历片段和岗位要求生成向量。
    chunks = _split_evidence_units(resume_text)
    vectors = _embed_in_batches([*chunks, *requirements])
    chunk_vectors = vectors[:len(chunks)]
    requirement_vectors = vectors[len(chunks):]
    details = []

    # 逐条岗位要求寻找最相似的简历证据。
    for requirement, requirement_vector in zip(requirements, requirement_vectors):
        scores = [_cosine_similarity(requirement_vector, chunk_vector) for chunk_vector in chunk_vectors]
        best_index = max(range(len(scores)), key=scores.__getitem__)
        best_score, evidence, method = scores[best_index], chunks[best_index], "semantic"

        # 达到配置的阈值，才认为该岗位要求被简历证据匹配到。
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

    # 汇总匹配项、缺失项，并计算整体匹配比例。
    matched = [item["requirement"] for item in details if item["matched"]]
    missing = [item["requirement"] for item in details if not item["matched"]]
    return {"score": round(len(matched) / len(requirements), 2), "matched": matched, "missing": missing, "details": details, "threshold": settings.SEMANTIC_MATCH_THRESHOLD}


SEMANTIC_MATCH_TOOLS = [semantic_match]
