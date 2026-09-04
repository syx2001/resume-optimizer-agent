"""Public schema exports used by the resume optimization agent."""

from app.schemas.job import JobDescriptionInput, JobProfile
from app.schemas.optimization import MatchResult, OptimizationPlan, ResumeChange
from app.schemas.resume import ResumeInput, ResumeProfile
from app.schemas.responses import RewriteResult, ResumeOptimizationResult, ValidationResult

__all__ = [
    "ResumeInput",
    "ResumeProfile",
    "JobDescriptionInput",
    "JobProfile",
    "MatchResult",
    "OptimizationPlan",
    "ResumeChange",
    "RewriteResult",
    "ValidationResult",
    "ResumeOptimizationResult",
]
