# app/rag/splitter.py

from langchain_text_splitters import RecursiveCharacterTextSplitter


text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=150,
)


def split_text(text: str) -> list[str]:
    return text_splitter.split_text(text)

def split_pages(
    pages: list[dict],
) -> list[dict]:

    chunks = []

    for page in pages:

        page_chunks = text_splitter.split_text(
            page["content"]
        )

        for chunk in page_chunks:
            chunks.append(
                {
                    "page_number": page["page_number"],
                    "content": chunk,
                }
            )

    return chunks