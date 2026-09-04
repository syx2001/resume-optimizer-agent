"""Delete all user-scoped long-term data from the LangGraph Store.

This removes data under the ``("users",)`` namespace, including saved
resumes and long-term memories. It does not delete RAG data or checkpoints.

Run from the project root:

    python scripts/reset_user_data.py

For a non-interactive development reset:

    python scripts/reset_user_data.py --yes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.infrastructure.database.postgres import (  # noqa: E402
    close_database,
    initialize_database,
)


def reset_all_user_data() -> int:
    resources = initialize_database()
    try:
        # Store search uses a namespace prefix, so this includes every user
        # namespace such as users/<user_id>/memories and users/<user_id>/resume.
        items = resources.store.search(("users",), limit=10000)
        deleted = 0

        for item in items:
            namespace = getattr(item, "namespace", None)
            key = getattr(item, "key", None)
            if namespace is None or key is None:
                continue
            resources.store.delete(namespace, key)
            deleted += 1

        return deleted
    finally:
        close_database()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reset all user resumes and long-term memories."
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt; use only in development.",
    )
    args = parser.parse_args()

    if not args.yes:
        print("This will delete all saved resumes and long-term memories.")
        print("RAG documents and LangGraph checkpoints will not be deleted.")
        confirmation = input('Type "RESET_USERS" to continue: ').strip()
        if confirmation != "RESET_USERS":
            print("Cancelled.")
            return

    deleted = reset_all_user_data()
    print(f"Deleted {deleted} user-store records.")


if __name__ == "__main__":
    main()
