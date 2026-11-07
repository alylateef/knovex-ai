"""
Knovex AI - Unit Tests for Document Loader & Chunking
"""

import tempfile
from pathlib import Path
import pytest
from knovex.document_loader import parse_and_chunk_document


def test_txt_chunking_and_metadata_preservation():
    sample_text = (
        "Knovex AI is an enterprise RAG platform.\n\n"
        "It supports multi-tenancy, hybrid search, and Grok LLM integration.\n\n"
        "The retrieval pipeline combines dense vectors with BM25 sparse vectors and RRF fusion."
    )

    with tempfile.NamedTemporaryFile("w+", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(sample_text)
        temp_path = Path(f.name)

    try:
        chunks = parse_and_chunk_document(
            file_path=temp_path,
            document_id="doc-123",
            tenant_id="tenant-xyz",
            chunk_size=100,
            chunk_overlap=20,
        )

        assert len(chunks) > 0
        for i, chunk in enumerate(chunks):
            assert chunk.metadata["document_id"] == "doc-123"
            assert chunk.metadata["tenant_id"] == "tenant-xyz"
            assert chunk.metadata["source"] == temp_path.name
            assert chunk.metadata["page"] == 1
            assert chunk.metadata["chunk_index"] == i
            assert len(chunk.page_content) > 0
    finally:
        if temp_path.exists():
            temp_path.unlink()


def test_empty_file_handling():
    with tempfile.NamedTemporaryFile("w+", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("")
        temp_path = Path(f.name)

    try:
        chunks = parse_and_chunk_document(
            file_path=temp_path,
            document_id="doc-empty",
            tenant_id="tenant-xyz",
        )
        assert chunks == []
    finally:
        if temp_path.exists():
            temp_path.unlink()


def test_pdf_table_detection_and_chunking():
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Overview: Financial breakdown.")
    page.draw_rect(pymupdf.Rect(50, 80, 300, 150))
    page.draw_line((50, 115), (300, 115))
    page.draw_line((175, 80), (175, 150))
    page.insert_text((60, 100), "Category")
    page.insert_text((185, 100), "Amount")
    page.insert_text((60, 135), "Revenue")
    page.insert_text((185, 135), "$500,000")
    page.insert_text((50, 180), "Conclusion: Targets exceeded.")

    temp_path = Path(tempfile.gettempdir()) / "test_table_doc.pdf"
    doc.save(str(temp_path))
    doc.close()

    try:
        chunks = parse_and_chunk_document(
            file_path=temp_path,
            document_id="doc-pdf-table",
            tenant_id="tenant-xyz",
        )

        assert len(chunks) >= 2
        # Check that table chunk is marked with is_table and has markdown format
        table_chunks = [c for c in chunks if c.metadata.get("is_table")]
        assert len(table_chunks) >= 1
        assert "|" in table_chunks[0].page_content
        assert table_chunks[0].metadata["page"] == 1

        # Check prose chunk
        prose_chunks = [c for c in chunks if not c.metadata.get("is_table")]
        assert len(prose_chunks) >= 1
        assert "Overview: Financial breakdown." in prose_chunks[0].page_content
    finally:
        if temp_path.exists():
            temp_path.unlink()


def test_docx_parsing_and_table_preservation():
    import docx

    doc = docx.Document()
    doc.add_paragraph("Knovex Executive Summary for Word Documents.")

    # Add a table
    table = doc.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "Metric"
    table.rows[0].cells[1].text = "Value"
    table.rows[1].cells[0].text = "Uptime"
    table.rows[1].cells[1].text = "99.9%"

    doc.add_paragraph("Concluding remarks on enterprise reliability.")

    temp_path = Path(tempfile.gettempdir()) / "test_doc.docx"
    doc.save(str(temp_path))

    try:
        chunks = parse_and_chunk_document(
            file_path=temp_path,
            document_id="doc-docx-test",
            tenant_id="tenant-xyz",
        )

        assert len(chunks) >= 2
        # Verify table chunk
        table_chunks = [c for c in chunks if c.metadata.get("is_table")]
        assert len(table_chunks) >= 1
        assert "| Metric | Value |" in table_chunks[0].page_content
        assert "| Uptime | 99.9% |" in table_chunks[0].page_content

        # Verify prose chunk
        prose_chunks = [c for c in chunks if not c.metadata.get("is_table")]
        assert any("Knovex Executive Summary" in c.page_content for c in prose_chunks)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def test_csv_parsing_and_header_preservation():
    csv_content = (
        "Name,Role,Department,Salary\n"
        "Alice Smith,Engineer,R&D,120000\n"
        "Bob Jones,Analyst,Finance,95000\n"
        "Carol White,Manager,Sales,110000\n"
    )

    temp_path = Path(tempfile.gettempdir()) / "test_data.csv"
    temp_path.write_text(csv_content, encoding="utf-8")

    try:
        chunks = parse_and_chunk_document(
            file_path=temp_path,
            document_id="doc-csv-test",
            tenant_id="tenant-xyz",
        )

        assert len(chunks) >= 1
        c = chunks[0]
        assert c.metadata.get("is_table") is True
        assert "| Name | Role | Department | Salary |" in c.page_content
        assert "| Alice Smith | Engineer | R&D | 120000 |" in c.page_content
        assert "| Bob Jones | Analyst | Finance | 95000 |" in c.page_content
    finally:
        if temp_path.exists():
            temp_path.unlink()
