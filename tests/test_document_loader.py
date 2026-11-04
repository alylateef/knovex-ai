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
