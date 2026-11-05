from pathlib import Path
import re
from typing import List, Optional
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from knovex.config import get_settings

settings = get_settings()

# Matches a full markdown table: header row + separator row + 1+ data rows
_TABLE_RE = re.compile(
    r'(\|.+\|\n\|[-| :]+\|\n(?:\|.+\|\n?)+)',
    re.MULTILINE,
)


def _split_page_text(
    page_text: str,
    filename: str,
    page_num: int,
    text_splitter: RecursiveCharacterTextSplitter,
) -> List[Document]:
    """
    Splits a single page's markdown text into chunks while keeping tables atomic.
    Tables are never split mid-row; surrounding prose is split normally.
    """
    docs: List[Document] = []
    last_end = 0

    for match in _TABLE_RE.finditer(page_text):
        # --- Prose before this table ---
        pre = page_text[last_end : match.start()].strip()
        if pre:
            for chunk in text_splitter.split_documents(
                [Document(page_content=pre, metadata={"source": filename, "page": page_num})]
            ):
                docs.append(chunk)

        # --- Table as one atomic chunk (never split) ---
        docs.append(Document(
            page_content=match.group(0).strip(),
            metadata={"source": filename, "page": page_num, "is_table": True},
        ))
        last_end = match.end()

    # --- Prose after last table (or full page if no tables) ---
    remaining = page_text[last_end:].strip()
    if remaining:
        for chunk in text_splitter.split_documents(
            [Document(page_content=remaining, metadata={"source": filename, "page": page_num})]
        ):
            docs.append(chunk)

    return docs


def parse_and_chunk_document(
    file_path: Path,
    document_id: str,
    tenant_id: str,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> List[Document]:
    """
    Parses and chunks uploaded documents into structured passages.

    PDF pipeline:
      - pymupdf4llm (page_chunks=True) → real page numbers + markdown per page
      - Tables detected via regex and kept as atomic chunks (never split mid-row)
      - Prose split with RecursiveCharacterTextSplitter (same behaviour as before)

    TXT / MD pipeline: unchanged from original.
    """
    from langchain_community.document_loaders import TextLoader

    chunk_size = chunk_size or settings.CHUNK_SIZE
    chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    file_ext = file_path.suffix.lower()
    filename = file_path.name

    # ------------------------------------------------------------------
    # PDF — pymupdf4llm with page_chunks=True for real page metadata
    # ------------------------------------------------------------------
    if file_ext == ".pdf":
        import pymupdf4llm

        # Returns list of {"metadata": {"page": 0, ...}, "text": "..."} per page
        page_data_list = pymupdf4llm.to_markdown(str(file_path), page_chunks=True)
        total_pages = len(page_data_list)

        split_docs: List[Document] = []
        for page_data in page_data_list:
            real_page = int(page_data["metadata"].get("page", 0)) + 1  # 1-based
            page_text = page_data["text"]
            split_docs.extend(_split_page_text(page_text, filename, real_page, text_splitter))

    # ------------------------------------------------------------------
    # TXT / MD — unchanged original behaviour
    # ------------------------------------------------------------------
    elif file_ext in {".txt", ".md"}:
        loader = TextLoader(str(file_path), encoding="utf-8")
        raw_docs = loader.load()
        split_docs = text_splitter.split_documents(raw_docs)
        total_pages = 1

    else:
        raise ValueError(f"Unsupported file type: {file_ext}")

    # ------------------------------------------------------------------
    # Attach tenant + index metadata to every chunk
    # ------------------------------------------------------------------
    chunks: List[Document] = []
    for idx, doc in enumerate(split_docs):
        content = doc.page_content.strip()
        if not content:
            continue

        page_num = doc.metadata.get("page", 1)

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
                    "is_table": doc.metadata.get("is_table", False),
                },
            )
        )

    return chunks




