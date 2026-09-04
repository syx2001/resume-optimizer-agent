from langchain_core.tools import tool


@tool
def check_keyword_coverage(
    resume_text: str,
    keywords: list[str],
) -> dict:
    """Match a resume against a job's keywords.

    Use this tool during resume-to-job matching when you need objective
    keyword coverage evidence. It performs a case-insensitive literal
    substring check and returns the matched keywords, missing keywords, and
    a coverage score from 0 to 1.

    The tool is read-only: it does not rewrite the resume, infer skills,
    judge semantic equivalence, or prove that a candidate has a skill.
    Treat the result as supporting evidence and combine it with the parsed
    resume and job profiles when producing the final MatchResult.
    """
    text = resume_text.casefold()
    matched = [keyword for keyword in keywords if keyword.casefold() in text]
    missing = [keyword for keyword in keywords if keyword.casefold() not in text]
    score = len(matched) / len(keywords) if keywords else 1.0
    return {
        "score": round(score, 2),
        "matched": matched,
        "missing": missing,
    }


@tool
def search_resume_guidelines(query: str) -> dict:
    """Search resume or ATS guidelines."""
    return {
        "query": query,
        "sources": [],
    }


RESUME_TOOLS = [
    check_keyword_coverage,
    search_resume_guidelines,
]
