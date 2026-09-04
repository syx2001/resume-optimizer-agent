from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.optimization import MatchResult, ResumeChange


class RewriteResult(BaseModel):
    """Structured result of one resume rewrite."""

    content: str
    changes: list[ResumeChange] = Field(default_factory=list)


class ValidationResult(BaseModel):
    """Result of one resume validation check."""

    category: Literal["fact", "keyword", "format", "quality"]
    passed: bool
    message: str
    repairable: bool = True
    suggestion: str | None = None


class ResumeOptimizationResult(BaseModel):
    """Final structured result of the resume optimization workflow."""

    status: Literal["completed", "blocked", "failed"]
    optimized_resume: str | None = None
    match_result: MatchResult | None = None
    changes: list[ResumeChange] = Field(default_factory=list)
    validation_results: list[ValidationResult] = Field(default_factory=list)
    error: str | None = None
