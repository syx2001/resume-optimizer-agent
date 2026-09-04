from datetime import datetime

from pydantic import BaseModel


#resume闀挎湡璁板繂鐩稿叧
class StoredResume(BaseModel):
    resume_id: str
    user_id: str
    content: str
    # SHA-256 of normalized resume content, used to avoid duplicate writes.
    # Optional for compatibility with records created before hash support.
    content_hash: str | None = None
    language: str = "auto"
    profile: dict | None = None
    source_name: str | None = None
    is_default: bool = True
    created_at: datetime
    updated_at: datetime
