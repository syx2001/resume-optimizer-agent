from datetime import datetime, timezone
import uuid
from hashlib import sha256

from app.memory.models import StoredResume
from app.memory.repository import ResumeRepository
from app.schemas import ResumeInput, ResumeProfile

class ResumeService:
    def __init__(
        self,
        repository: ResumeRepository,
    ):
        self.repository = repository
    def get_default(
          self,
          user_id: str,
      ) -> StoredResume | None:
          return self.repository.get_default(user_id)

    @staticmethod
    def make_content_hash(content: str) -> str:
        """Hash normalized resume text so whitespace does not cause a rewrite."""
        normalized = "\n".join(
            line.strip()
            for line in content.splitlines()
            if line.strip()
        )
        return sha256(normalized.encode("utf-8")).hexdigest()

    def save_default(
        self,
        user_id: str,
        resume_input: ResumeInput,
        resume_profile: ResumeProfile,
    ) -> StoredResume:
        old_resume = self.repository.get_default(user_id)
        content = resume_input.content.strip()
        content_hash = self.make_content_hash(content)

        # Avoid rewriting the Store when the actual resume content has not
        # changed. The content fallback keeps old records without a hash
        # readable after this field is introduced.
        if old_resume:
            old_hash = old_resume.content_hash
            same_legacy_content = (
                old_hash is None
                and self.make_content_hash(old_resume.content) == content_hash
            )
            if old_hash == content_hash:
                return old_resume
            if same_legacy_content:
                # One-time backfill for records created before content_hash.
                old_resume.content_hash = content_hash
                self.repository.save_default(old_resume)
                return old_resume

        now = datetime.now(timezone.utc)

        resume = StoredResume(
            resume_id=(
                old_resume.resume_id
                if old_resume
                else uuid.uuid4().hex
            ),
            user_id=user_id,
            content=content,
            content_hash=content_hash,
            language=resume_input.language,
            profile=resume_profile.model_dump(),
            source_name=None,
            is_default=True,
            created_at=(
                old_resume.created_at
                if old_resume
                else now
            ),
            updated_at=now,
        )
        print("save resume")
        self.repository.save_default(resume)
        return resume
      
