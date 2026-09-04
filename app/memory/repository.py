from langgraph.store.base import BaseStore

from app.memory.models import StoredResume


class ResumeRepository:
    def __init__(self, store: BaseStore):
        self.store = store

    def _namespace(self, user_id: str) -> tuple:
        return ("users", user_id, "resume")

    def get_default(self, user_id: str) -> StoredResume | None:
        item = self.store.get(self._namespace(user_id), "default")
        if not item:
            return None
        return StoredResume.model_validate(item.value)

    def save_default(self, resume: StoredResume) -> None:
        self.store.put(
            self._namespace(resume.user_id),
            "default",
            resume.model_dump(mode="json"),
        )
