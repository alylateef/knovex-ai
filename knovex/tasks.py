"""
Knovex AI - Background Ingestion Tasks
Handles asynchronous document chunking, embedding, Qdrant upsert, and DB status tracking
using asyncio.to_thread and FastAPI BackgroundTasks.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from sqlalchemy import select

from knovex.config import get_settings
from knovex.database import get_sync_db_context
from knovex.document_loader import parse_and_chunk_document
from knovex.models import Document, DocumentChunk, IngestionJob
from knovex.rag import get_vector_store

logger = logging.getLogger(__name__)
settings = get_settings()


def run_ingestion_pipeline(document_id: str, tenant_id: str) -> bool:
    """
    Executes background document ingestion pipeline:
    1. Loads document content and computes chunk splits
    2. Generates dense and sparse embeddings
    3. Indexes vectors in Qdrant with tenant isolation
    4. Records chunk records and updates job status in PostgreSQL
    """
    try:
        with get_sync_db_context() as db:
            # 1. Fetch document and job records
            doc = db.execute(
                select(Document).where(Document.id == document_id, Document.tenant_id == tenant_id)
            ).scalar_one_or_none()
            if not doc:
                logger.error(f"Document {document_id} not found for tenant {tenant_id}")
                return False

            job = db.execute(
                select(IngestionJob).where(
                    IngestionJob.document_id == document_id,
                    IngestionJob.tenant_id == tenant_id
                )
            ).scalar_one_or_none()

            if job:
                job.status = "PROCESSING"
                job.progress_percent = 20
                job.started_at = datetime.now(timezone.utc)
                db.commit()

            # 2. Parse & chunk document
            file_path = Path(doc.file_path)
            chunks = parse_and_chunk_document(
                file_path=file_path,
                document_id=document_id,
                tenant_id=tenant_id,
                chunk_size=settings.CHUNK_SIZE,
                chunk_overlap=settings.CHUNK_OVERLAP,
            )

            if job:
                job.progress_percent = 50
                db.commit()

            # 3. Upsert chunks into Qdrant
            if chunks:
                store = get_vector_store()
                chunk_ids = [
                    str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document_id}/{c.metadata['chunk_index']}"))
                    for c in chunks
                ]
                batch_size = 128
                total_batches = (len(chunks) + batch_size - 1) // batch_size
                for b_idx in range(total_batches):
                    start = b_idx * batch_size
                    end = min(start + batch_size, len(chunks))
                    store.add_documents(documents=chunks[start:end], ids=chunk_ids[start:end])
                    if job:
                        # Scale progress from 50% to 90% across embedding batches
                        job.progress_percent = 50 + int((b_idx + 1) / total_batches * 40)
                        db.commit()

                # 4. Save chunk records in PostgreSQL
                # Remove any existing chunks for idempotency
                existing_chunks = db.execute(
                    select(DocumentChunk).where(DocumentChunk.document_id == document_id)
                ).scalars().all()
                for ec in existing_chunks:
                    db.delete(ec)

                chunk_records = [
                    DocumentChunk(
                        tenant_id=tenant_id,
                        document_id=document_id,
                        chunk_index=c.metadata.get("chunk_index", i),
                        page_number=c.metadata.get("page", 1),
                        content=c.page_content.replace("\x00", ""),
                        qdrant_point_id=chunk_ids[i],
                        char_count=len(c.page_content),
                    )
                    for i, c in enumerate(chunks)
                ]
                db.add_all(chunk_records)

                total_pages_val = chunks[0].metadata.get("total_pages", 1) if (chunks and "total_pages" in chunks[0].metadata) else 1
                doc.total_chunks = len(chunks)
                doc.total_pages = total_pages_val

                from sqlalchemy import update
                db.execute(
                    update(Document)
                    .where(Document.id == document_id)
                    .values(total_chunks=len(chunks), total_pages=total_pages_val)
                )

            # 5. Mark as completed
            if job:
                job.status = "COMPLETED"
                job.progress_percent = 100
                job.completed_at = datetime.now(timezone.utc)
            db.commit()
            logger.info(f"Successfully ingested {len(chunks)} chunks for document {document_id}")
            return True

    except Exception as e:
        logger.exception(f"Ingestion failed for doc {document_id}: {e}")
        try:
            with get_sync_db_context() as err_db:
                job = err_db.execute(
                    select(IngestionJob).where(
                        IngestionJob.document_id == document_id,
                        IngestionJob.tenant_id == tenant_id
                    )
                ).scalar_one_or_none()
                if job:
                    job.status = "FAILED"
                    job.error_message = str(e)
        except Exception:
            pass
        return False



async def start_async_ingestion(document_id: str, tenant_id: str) -> None:
    """Non-blocking background ingestion runner using asyncio.to_thread."""
    await asyncio.to_thread(run_ingestion_pipeline, document_id, tenant_id)

