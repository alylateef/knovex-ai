from pathlib import Path
from typing import List, Optional
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

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
    Preserves document, tenant, and page metadata across chunk boundaries.
    """
    from langchain_community.document_loaders import PyMuPDFLoader, TextLoader

    chunk_size = chunk_size or settings.CHUNK_SIZE
    chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

    # Recursive chunking with overlap across paragraph and sentence boundaries
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    file_ext = file_path.suffix.lower()
    filename = file_path.name

    # 1. Document loader selection
    if file_ext == ".pdf":
        loader = PyMuPDFLoader(str(file_path))
        raw_docs = loader.load()
    elif file_ext in {".txt", ".md"}:
        loader = TextLoader(str(file_path), encoding="utf-8")
        raw_docs = loader.load()
    else:
        raise ValueError(f"Unsupported file type: {file_ext}")

    total_pages = len(raw_docs) if file_ext == ".pdf" else 1

    # 2. Split into overlapping chunks
    split_docs = text_splitter.split_documents(raw_docs)

    # 3. Attach tenant and index metadata
    chunks: List[Document] = []
    for idx, doc in enumerate(split_docs):
        content = doc.page_content.strip()
        if not content:
            continue

        page_num = doc.metadata.get("page", 0) + 1 if file_ext == ".pdf" else 1

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




