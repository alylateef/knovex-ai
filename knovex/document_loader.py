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

    PDF parsing:
      - Uses PyMuPDF's built-in table engine to identify tabular data.
      - Tables are preserved as atomic Markdown chunks (never broken mid-row).
      - Surrounding prose text is split with RecursiveCharacterTextSplitter as normal.
      - Requires zero external dependencies.

    TXT / MD:
      - Cleanly parsed with standard TextLoader and chunked.
    """
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
    all_split_docs: List[Document] = []

    if file_ext == ".pdf":
        import pymupdf

        doc = pymupdf.open(str(file_path))
        total_pages = len(doc)

        for page_idx, page in enumerate(doc):
            page_num = page_idx + 1

            # Detect any tables on the current page
            tabs = page.find_tables()
            tab_rects = [pymupdf.Rect(t.bbox) for t in tabs] if tabs and tabs.tables else []

            if tab_rects:
                # 1. Preserve tables as atomic markdown chunks
                for t in tabs:
                    table_md = t.to_markdown().strip()
                    if table_md:
                        all_split_docs.append(
                            Document(
                                page_content=table_md,
                                metadata={"page": page_num, "is_table": True},
                            )
                        )

                # 2. Extract surrounding prose text outside of table bounding boxes
                blocks = page.get_text("blocks")
                prose_parts = []
                for b in blocks:
                    r = pymupdf.Rect(b[:4])
                    if not any(r.intersects(tr) for tr in tab_rects):
                        prose_parts.append(b[4])

                prose_text = "".join(prose_parts).strip()
                if prose_text:
                    prose_chunks = text_splitter.split_documents([
                        Document(page_content=prose_text, metadata={"page": page_num})
                    ])
                    all_split_docs.extend(prose_chunks)

            else:
                # Standard text page: identical to original behavior
                page_text = page.get_text().strip()
                if page_text:
                    page_chunks = text_splitter.split_documents([
                        Document(page_content=page_text, metadata={"page": page_num})
                    ])
                    all_split_docs.extend(page_chunks)

        doc.close()

    elif file_ext in {".txt", ".md"}:
        from langchain_community.document_loaders import TextLoader

        loader = TextLoader(str(file_path), encoding="utf-8")
        raw_docs = loader.load()
        total_pages = 1
        all_split_docs = text_splitter.split_documents(raw_docs)

    else:
        raise ValueError(f"Unsupported file type: {file_ext}")

    # Attach tenant, document and index metadata to every chunk
    chunks: List[Document] = []
    for idx, doc_item in enumerate(all_split_docs):
        content = doc_item.page_content.strip()
        if not content:
            continue

        page_num = doc_item.metadata.get("page", 1)
        meta = {
            "tenant_id": tenant_id,
            "document_id": document_id,
            "source": filename,
            "page": page_num,
            "total_pages": total_pages,
            "chunk_index": idx,
        }
        if doc_item.metadata.get("is_table"):
            meta["is_table"] = True

        chunks.append(
            Document(
                page_content=content,
                metadata=meta,
            )
        )

    return chunks
