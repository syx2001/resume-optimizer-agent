# app/rag/loader.py

from pathlib import Path
from pypdf import PdfReader

def load_text_file(file_path: str) -> str:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(file_path)

    if path.suffix.lower() not in {".txt", ".md"}:
        raise ValueError(
            f"Unsupported file type: {path.suffix}"
        )

    return path.read_text(
        encoding="utf-8"
    )

def load_pdf(file_path: str) -> list[dict]:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(file_path)

    reader = PdfReader(str(path))

    pages = []

    for page_number, page in enumerate(
        reader.pages,
        start=1,
    ):
        text = page.extract_text() or ""

        if not text.strip():
            continue

        pages.append(
            {
                "page_number": page_number,
                "content": text,
            }
        )

    return pages