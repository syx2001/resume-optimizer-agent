from pydantic import BaseModel, Field


class ResumeInput(BaseModel):
    content: str
    language: str = "auto"


class ResumeProfile(BaseModel):
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    experiences: list[dict] = Field(default_factory=list)
    projects: list[dict] = Field(default_factory=list)
