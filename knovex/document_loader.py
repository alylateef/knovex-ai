from pathlib import Path
from typing import List, Optional
from langchain_core.documents import Document
from langchain_text_splitters import MarkdownTextSplitter, RecursiveCharacterTextSplitter

from knovex.config import get_settings

settings = get_settings()


def parse_and_chunk_document(
    file_path: Path,
    document_id: str,
    tenant_id: str,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> List[Document]:
    """
    Parses and chunks uploaded documents into structured passages.
    Uses pymupdf4llm for PDFs — preserves tables as markdown, maintains headers.
    Preserves document, tenant, and page metadata across chunk boundaries.
    """
    from langchain_community.document_loaders import TextLoader

    chunk_size = chunk_size or settings.CHUNK_SIZE
    chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

    file_ext = file_path.suffix.lower()
    filename = file_path.name

    # 1. Document loader selection
    if file_ext == ".pdf":
        # pymupdf4llm converts PDF → Markdown, preserving tables and structure
        import pymupdf4llm
        md_text = pymupdf4llm.to_markdown(str(file_path))

        # Split markdown-aware: respects headers and table boundaries
        text_splitter = MarkdownTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        raw_docs = [Document(page_content=md_text, metadata={"source": filename, "page": 0})]

    elif file_ext in {".txt", ".md"}:
        loader = TextLoader(str(file_path), encoding="utf-8")
        raw_docs = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
    else:
        raise ValueError(f"Unsupported file type: {file_ext}")

    # 2. Split into overlapping chunks
    split_docs = text_splitter.split_documents(raw_docs)
    total_pages = len(split_docs) if file_ext == ".pdf" else 1

    # 3. Attach tenant and index metadata
    chunks: List[Document] = []
    for idx, doc in enumerate(split_docs):
        content = doc.page_content.strip()
        if not content:
            continue

        # For markdown-converted PDFs, page is estimated by chunk index
        page_num = (idx // max(1, len(split_docs) // max(1, total_pages))) + 1 if file_ext == ".pdf" else 1

        chunks.append(
            Document(
                page_content=content,
                metadata={
                    "tenant_id": tenant_id,
                    "document_id": document_id,
                    "source": filename,
                    "page": page_num,
                    "total_pages": total_pages,
                    "chunk_index": idx,
                },
            )
        )

    return chunks




