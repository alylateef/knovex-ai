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

    elif file_ext == ".docx":
        import docx

        doc = docx.Document(str(file_path))
        total_pages = 1

        # Sequential extraction: iterate through document body elements in order
        for child in doc.element.body.iterchildren():
            if child.tag.endswith("p"):
                # Extract paragraph text
                text = "".join(node.text for node in child.iter() if node.tag.endswith("t") and node.text).strip()
                if text:
                    p_chunks = text_splitter.split_documents([
                        Document(page_content=text, metadata={"page": 1})
                    ])
                    all_split_docs.extend(p_chunks)

            elif child.tag.endswith("tbl"):
                # Extract table as structured Markdown
                from docx.table import Table

                t = Table(child, doc)
                rows_data = []
                for row in t.rows:
                    row_cells = [cell.text.replace("\n", " ").replace("|", "/").strip() for cell in row.cells]
                    rows_data.append(row_cells)

                if rows_data:
                    header = rows_data[0]
                    col_count = max(len(header), 1)
                    md_lines = [
                        "| " + " | ".join(header) + " |",
                        "| " + " | ".join(["---"] * col_count) + " |",
                    ]
                    for r in rows_data[1:]:
                        padded = r + [""] * (col_count - len(r)) if len(r) < col_count else r[:col_count]
                        md_lines.append("| " + " | ".join(padded) + " |")

                    table_md = "\n".join(md_lines).strip()
                    if table_md:
                        all_split_docs.append(
                            Document(page_content=table_md, metadata={"page": 1, "is_table": True})
                        )

        # Safety fallback: if iterchildren() extracted no chunks, use standard doc.paragraphs
        if not all_split_docs and doc.paragraphs:
            full_text = "\n\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())
            if full_text:
                all_split_docs = text_splitter.split_documents([
                    Document(page_content=full_text, metadata={"page": 1})
                ])

    elif file_ext == ".csv":
        import csv
        import io

        total_pages = 1

        # Safe encoding detection (Excel utf-8-sig BOM, utf-8, latin-1)
        raw_text = None
        for enc in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                with open(file_path, "r", encoding=enc) as f:
                    raw_text = f.read()
                break
            except (UnicodeDecodeError, LookupError):
                continue

        if not raw_text:
            raise ValueError("Could not decode CSV file content.")

        reader = csv.reader(io.StringIO(raw_text))
        rows = list(reader)

        if rows:
            clean_rows = [
                [cell.replace("\n", " ").replace("|", "/").strip() for cell in row]
                for row in rows
                if any(cell.strip() for cell in row)
            ]
            if clean_rows:
                header = clean_rows[0]
                col_count = max(len(header), 1)
                data_rows = clean_rows[1:]

                header_md = "| " + " | ".join(header) + " |"
                sep_md = "| " + " | ".join(["---"] * col_count) + " |"
                base_header_lines = [header_md, sep_md]
                base_header_chars = len(header_md) + len(sep_md) + 2

                if not data_rows:
                    all_split_docs.append(
                        Document(page_content="\n".join(base_header_lines), metadata={"page": 1, "is_table": True})
                    )
                else:
                    # Dynamic character-aware table chunking:
                    # Target ~800-1000 characters per chunk (max 8 rows) to strictly prevent LLM context overflow
                    # while preserving tabular markdown headers on every chunk for retrieval accuracy.
                    target_chunk_chars = chunk_size or settings.CHUNK_SIZE
                    current_rows: List[str] = []
                    current_chars = base_header_chars
                    chunk_page = 1

                    for row in data_rows:
                        padded = row + [""] * (col_count - len(row)) if len(row) < col_count else row[:col_count]
                        row_line = "| " + " | ".join(padded) + " |"
                        row_chars = len(row_line) + 1

                        # If adding this row exceeds target and we already have rows, flush chunk
                        if current_rows and ((current_chars + row_chars > target_chunk_chars) or len(current_rows) >= 8):
                            table_md = "\n".join(base_header_lines + current_rows).strip()
                            all_split_docs.append(
                                Document(page_content=table_md, metadata={"page": chunk_page, "is_table": True})
                            )
                            chunk_page += 1
                            current_rows = [row_line]
                            current_chars = base_header_chars + row_chars
                        else:
                            current_rows.append(row_line)
                            current_chars += row_chars

                    if current_rows:
                        table_md = "\n".join(base_header_lines + current_rows).strip()
                        all_split_docs.append(
                            Document(page_content=table_md, metadata={"page": chunk_page, "is_table": True})
                        )

                total_pages = max(1, len(all_split_docs))

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
