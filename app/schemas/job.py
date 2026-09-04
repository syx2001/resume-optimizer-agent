from pydantic import BaseModel, Field


class JobDescriptionInput(BaseModel):
    content: str  # 原始职位描述
    role_title: str | None = None  # 目标职位名称


class JobProfile(BaseModel):
    responsibilities: list[str] = Field(default_factory=list)  # 岗位职责
    required_skills: list[str] = Field(default_factory=list)  # 必需技能
    keywords: list[str] = Field(default_factory=list)  # JD 关键词