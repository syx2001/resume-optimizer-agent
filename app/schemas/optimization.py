from pydantic import BaseModel, Field


class ResumeChange(BaseModel):
    section: str  # 被修改的简历部分
    original: str  # 修改前内容
    revised: str  # 修改后内容
    reason: str  # 修改原因


class MatchResult(BaseModel):
    score: float  # 岗位匹配分数，建议范围为 0 到 1
    matched: list[str] = Field(default_factory=list)  # 已匹配要求
    missing: list[str] = Field(default_factory=list)  # 缺失要求


class OptimizationPlan(BaseModel):
    goals: list[str]  # 优化目标
    steps: list[str]  # 优化步骤