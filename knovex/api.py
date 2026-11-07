"""
Knovex AI - Main API Router
Implements Auth, Tenant-isolated Documents, and Chat endpoints.
"""

import asyncio
from functools import lru_cache
import logging
import uuid
from typing import List, Optional
from pathlib import Path
import redis.asyncio as aioredis
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Security, UploadFile, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from qdrant_client.http import models as qmodels

from knovex.config import get_settings
from knovex.database import get_async_db
from knovex.models import (
    Conversation,
    Document,
    DocumentChunk,
    IngestionJob,
    Message,
    Tenant,
    User,
)
from knovex.rag import get_qdrant_client, run_rag_pipeline, stream_rag_pipeline
from knovex.schemas import (
    ChatMessageRequest,
    ChatMessageResponse,
    CitationItem,
    ConversationDetailOut,
    ConversationOut,
    ConversationPatchRequest,
    DocumentOut,
    DocumentUploadResponse,
    IngestionStatusOut,
    JoinRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from knovex.security import (
    check_rate_limit,
    create_access_token,
    decode_access_token,
    hash_password,
    is_token_revoked,
    revoke_token,
    verify_password,
)
from knovex.storage import save_uploaded_file
from knovex.tasks import run_ingestion_pipeline

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/v1")
security_bearer = HTTPBearer(auto_error=False)

# Optional Redis client with connection pooling and timeouts
@lru_cache(maxsize=1)
def get_redis_client() -> Optional[aioredis.Redis]:
    try:
        return aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=1.0,
            socket_connect_timeout=1.0,
        )
    except Exception:
        return None


async def get_redis() -> Optional[aioredis.Redis]:
    client = get_redis_client()
    if client:
        try:
            await client.ping()
            return client
        except Exception:
            return None
    return None


# ---------------------------------------------------------
# Dependencies: Auth & Rate Limiting
# ---------------------------------------------------------

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    db: AsyncSession = Depends(get_async_db),
    redis: Optional[aioredis.Redis] = Depends(get_redis),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token = credentials.credentials
    # Check Redis revocation blacklist
    if await is_token_revoked(redis, token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")

    token_data = decode_access_token(token)
    if not token_data or not token_data.user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # Rate limiting check
    allowed, _ = await check_rate_limit(redis, identifier=token_data.user_id, limit=settings.RATE_LIMIT_REQUESTS_PER_MINUTE)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")

    user = await db.get(User, token_data.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or not found")

    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Enforces admin role for document management operations."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: only administrators can upload or delete documents",
        )
    return current_user


# ---------------------------------------------------------
# Auth Endpoints
# ---------------------------------------------------------

@router.post("/auth/register", response_model=TokenResponse)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_async_db)):
    """Registers a new tenant organization or joins an existing one with admin or member role."""
    clean_org_name = payload.organization_name.strip()
    if not clean_org_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization name is required")

    # Check if user email already exists
    existing_user = await db.execute(select(User).where(User.email == payload.email))
    if existing_user.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    # Generate unique org_code (e.g. FAST-9A2F) — slug is the only globally unique key
    code_prefix = "".join(c for c in clean_org_name.upper() if c.isalnum())[:8] or "ORG"
    unique_suffix = uuid.uuid4().hex[:4].upper()
    org_code = f"{code_prefix}-{unique_suffix}"

    # Always create a fresh tenant — name is NOT required to be globally unique
    tenant = Tenant(name=clean_org_name, slug=org_code)
    db.add(tenant)
    await db.flush()

    # Org creator is always the Admin/Owner of the new workspace
    user = User(
        tenant_id=tenant.id,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role="admin",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token, _ = create_access_token(user_id=user.id, tenant_id=tenant.id, role=user.role, email=user.email)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        user_id=user.id,
        tenant_id=tenant.id,
        role=user.role,
        email=user.email,
    )


@router.post("/auth/join", response_model=TokenResponse)
async def join_organization(payload: JoinRequest, db: AsyncSession = Depends(get_async_db)):
    """Allows a user to join an existing organization using its unique Org Code."""
    code = payload.org_code.strip()
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization code is required")

    # Check if user email already exists
    existing_user = await db.execute(select(User).where(User.email == payload.email))
    if existing_user.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered. Please sign in.")

    # Find tenant strictly by slug (org_code) only — name is NOT unique
    tenant_res = await db.execute(
        select(Tenant).where(Tenant.slug.ilike(code))
    )
    tenant = tenant_res.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization code '{code}' not found. Please verify the code with your administrator.",
        )

    # Teammate joining an existing workspace is always a standard User (Member)
    user = User(
        tenant_id=tenant.id,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role="user",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token, _ = create_access_token(user_id=user.id, tenant_id=tenant.id, role=user.role, email=user.email)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        user_id=user.id,
        tenant_id=tenant.id,
        role=user.role,
        email=user.email,
    )


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_async_db)):
    """Authenticates user and returns JWT access token."""
    res = await db.execute(select(User).where(User.email == payload.email))
    user = res.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account is deactivated")

    token, _ = create_access_token(user_id=user.id, tenant_id=user.tenant_id, role=user.role, email=user.email)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role,
        email=user.email,
    )


@router.post("/auth/logout")
async def logout(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    redis: Optional[aioredis.Redis] = Depends(get_redis),
):
    """Revokes the current user's JWT access token in Redis."""
    if credentials:
        await revoke_token(redis, credentials.credentials)
    return {"message": "Logged out successfully"}


@router.get("/auth/me", response_model=UserOut)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    tenant_res = await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))
    tenant = tenant_res.scalar_one_or_none()
    return UserOut(
        id=current_user.id,
        tenant_id=current_user.tenant_id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        organization_name=tenant.name if tenant else "",
        org_code=tenant.slug if tenant else "",
    )


# ---------------------------------------------------------
# Document Endpoints (Tenant-Isolated)
# ---------------------------------------------------------

@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """Uploads a PDF/TXT document and triggers asynchronous background ingestion via FastAPI BackgroundTasks."""
    # 1. Save and validate file safely
    saved_path, clean_name, file_size, mime, file_hash = await save_uploaded_file(current_user.tenant_id, file)

    # 1b. Reject duplicate uploads per tenant using SHA-256 hash
    existing_dup = await db.execute(
        select(Document).where(
            Document.tenant_id == current_user.tenant_id,
            Document.file_hash == file_hash,
        )
    )
    dup_doc = existing_dup.scalars().first()
    if dup_doc:
        if saved_path.exists():
            saved_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate document detected. This exact file already exists as '{dup_doc.filename}'."
        )

    # 2. Record document in database
    doc = Document(
        tenant_id=current_user.tenant_id,
        uploaded_by=current_user.id,
        filename=clean_name,
        file_path=str(saved_path),
        file_size=file_size,
        mime_type=mime,
        file_hash=file_hash,
    )
    db.add(doc)
    await db.flush()

    # 3. Create IngestionJob record
    job = IngestionJob(
        tenant_id=current_user.tenant_id,
        document_id=doc.id,
        status="PENDING",
    )
    db.add(job)
    await db.commit()
    await db.refresh(doc)
    await db.refresh(job)

    # 4. Trigger non-blocking native background ingestion (runs in threadpool, keeps event loop fast)
    background_tasks.add_task(run_ingestion_pipeline, doc.id, current_user.tenant_id)

    return DocumentUploadResponse(
        document_id=doc.id,
        filename=doc.filename,
        job_id=job.id,
        status="PENDING",
        message="Document uploaded and queued for ingestion",
    )


@router.get("/documents", response_model=List[DocumentOut])
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Lists all documents belonging to the authenticated tenant, with live ingestion status and dynamic chunk healing."""
    res = await db.execute(
        select(Document)
        .where(Document.tenant_id == current_user.tenant_id)
        .order_by(Document.created_at.desc())
    )
    docs = res.scalars().all()
    if not docs:
        return []

    doc_ids = [d.id for d in docs]
    jobs_res = await db.execute(
        select(IngestionJob)
        .where(
            IngestionJob.document_id.in_(doc_ids),
            IngestionJob.tenant_id == current_user.tenant_id,
        )
        .order_by(IngestionJob.created_at.desc())
    )
    all_jobs = jobs_res.scalars().all()
    job_map = {}
    for j in all_jobs:
        if j.document_id not in job_map:
            job_map[j.document_id] = j

    output = []
    needs_commit = False

    for d in docs:
        job = job_map.get(d.id)
        chunks_count = d.total_chunks

        # Self-healing: if total_chunks is 0, check DocumentChunk table or Qdrant points
        if chunks_count == 0:
            count_res = await db.execute(
                select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == d.id)
            )
            c_count = count_res.scalar() or 0
            if c_count > 0:
                chunks_count = c_count
                d.total_chunks = c_count
                needs_commit = True
            else:
                try:
                    q_client = get_qdrant_client()
                    filter_cond = qmodels.Filter(
                        must=[
                            qmodels.FieldCondition(
                                key="metadata.document_id",
                                match=qmodels.MatchValue(value=d.id),
                            ),
                            qmodels.FieldCondition(
                                key="metadata.tenant_id",
                                match=qmodels.MatchValue(value=current_user.tenant_id),
                            ),
                        ]
                    )
                    q_count = q_client.count(
                        collection_name=settings.QDRANT_COLLECTION_NAME,
                        count_filter=filter_cond,
                    ).count
                    if q_count > 0:
                        chunks_count = q_count
                        d.total_chunks = q_count
                        needs_commit = True
                except Exception:
                    pass

        status_val = job.status if job else ("COMPLETED" if chunks_count > 0 else "PENDING")
        progress_val = job.progress_percent if job else (100 if chunks_count > 0 else 0)
        error_val = job.error_message if job else None

        output.append(
            DocumentOut(
                id=d.id,
                tenant_id=d.tenant_id,
                filename=d.filename,
                file_size=d.file_size,
                mime_type=d.mime_type,
                total_pages=d.total_pages,
                total_chunks=chunks_count,
                created_at=d.created_at,
                status=status_val,
                progress_percent=progress_val,
                error_message=error_val,
            )
        )

    if needs_commit:
        try:
            await db.commit()
        except Exception:
            pass

    return output


@router.get("/documents/{document_id}/status", response_model=IngestionStatusOut)
async def get_ingestion_status(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Checks the background ingestion status for a document."""
    res = await db.execute(
        select(IngestionJob).where(
            IngestionJob.document_id == document_id,
            IngestionJob.tenant_id == current_user.tenant_id,
        )
    )
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    return job


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """Deletes a document, its database records, and its vectors from Qdrant."""
    res = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == current_user.tenant_id,
        )
    )
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete from Qdrant
    try:
        client = get_qdrant_client()
        filter_cond = qmodels.Filter(
            must=[
                qmodels.FieldCondition(key="metadata.tenant_id", match=qmodels.MatchValue(value=current_user.tenant_id)),
                qmodels.FieldCondition(key="metadata.document_id", match=qmodels.MatchValue(value=document_id)),
            ]
        )
        client.delete(collection_name=settings.QDRANT_COLLECTION_NAME, points_selector=qmodels.FilterSelector(filter=filter_cond))
    except Exception as e:
        logger.warning(f"Qdrant delete points error: {e}")

    # Delete physical file from disk
    try:
        Path(doc.file_path).unlink(missing_ok=True)
    except Exception as e:
        logger.warning(f"Could not delete physical file {doc.file_path}: {e}")

    await db.delete(doc)
    await db.commit()
    return {"message": "Document deleted successfully"}


# ---------------------------------------------------------
# Chat & RAG Endpoints
# ---------------------------------------------------------

@router.post("/chat/query", response_model=ChatMessageResponse)
async def chat_query(
    payload: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Executes the LangGraph RAG pipeline and returns grounded answers with validated citations."""
    # 1. Get or create conversation
    conv_id = payload.conversation_id
    if conv_id:
        conv = await db.get(Conversation, conv_id)
        if not conv or conv.tenant_id != current_user.tenant_id:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conv = Conversation(
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            title=payload.message[:50],
        )
        db.add(conv)
        await db.flush()
        conv_id = conv.id

    # 2. Save user message
    user_msg = Message(conversation_id=conv_id, role="user", content=payload.message)
    db.add(user_msg)
    await db.flush()

    # 3. Run LangGraph RAG pipeline with tenant isolation
    rag_result = run_rag_pipeline(
        question=payload.message,
        tenant_id=current_user.tenant_id,
        rerank=payload.rerank if payload.rerank is not None else True,
    )

    answer = rag_result.get("answer", "")
    citations_data = rag_result.get("citations", [])
    evidence_status = rag_result.get("evidence_status", "sufficient")

    # 4. Save assistant response
    assistant_msg = Message(
        conversation_id=conv_id,
        role="assistant",
        content=answer,
        citations=citations_data,
        evidence_status=evidence_status,
    )
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(assistant_msg)

    # 5. Format validated citations
    citation_items = [
        CitationItem(
            document_id=c.get("document_id", ""),
            filename=c.get("filename", ""),
            page_number=c.get("page_number", 1),
            chunk_index=c.get("chunk_index", 0),
            snippet=c.get("snippet", ""),
            relevance_score=float(c.get("relevance_score", 1.0)),
            validated=c.get("validated", True),
        )
        for c in citations_data
    ]

    return ChatMessageResponse(
        conversation_id=conv_id,
        message_id=assistant_msg.id,
        question=payload.message,
        answer=answer,
        evidence_status=evidence_status,
        citations=citation_items,
        retrieval_mode="hybrid_rrf",
        reranked=payload.rerank if payload.rerank is not None else True,
    )


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Streams RAG generation tokens live over Server-Sent Events (SSE)."""
    import json

    # 1. Get or create conversation
    conv_id = payload.conversation_id
    if conv_id:
        conv = await db.get(Conversation, conv_id)
        if not conv or conv.tenant_id != current_user.tenant_id:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conv = Conversation(
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            title=payload.message[:50],
        )
        db.add(conv)
        await db.flush()
        conv_id = conv.id

    # 2. Save user message
    user_msg = Message(conversation_id=conv_id, role="user", content=payload.message)
    db.add(user_msg)
    await db.commit()

    tenant_id = current_user.tenant_id
    question = payload.message
    rerank = payload.rerank if payload.rerank is not None else True

    async def event_generator():
        from knovex.database import get_sync_db_context
        # Yield initial conversation info
        yield f"data: {json.dumps({'type': 'init', 'conversation_id': conv_id})}\n\n"

        final_answer = ""
        final_citations = []
        final_evidence = "sufficient"
        all_metadata_citations = []

        for event in stream_rag_pipeline(question=question, tenant_id=tenant_id, rerank=rerank):
            if event["type"] == "metadata":
                all_metadata_citations = event.get("citations", [])
                yield f"data: {json.dumps(event)}\n\n"
                await asyncio.sleep(0)
            elif event["type"] == "delta":
                yield f"data: {json.dumps(event)}\n\n"
                await asyncio.sleep(0)
            elif event["type"] == "done":
                final_answer = event.get("answer", "")
                final_citations = event.get("citations", []) or all_metadata_citations
                final_evidence = event.get("evidence_status", "sufficient")
                yield f"data: {json.dumps(event)}\n\n"
                await asyncio.sleep(0)

        # Save assistant message in DB synchronously upon stream completion
        try:
            with get_sync_db_context() as sync_db:
                assistant_msg = Message(
                    conversation_id=conv_id,
                    role="assistant",
                    content=final_answer,
                    citations=final_citations or all_metadata_citations,
                    evidence_status=final_evidence,
                )
                sync_db.add(assistant_msg)
                sync_db.commit()
        except Exception as ex:
            logger.error(f"Failed to save assistant message from stream: {ex}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/chat/conversations", response_model=List[ConversationOut])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Lists conversations for authenticated user."""
    res = await db.execute(
        select(Conversation)
        .where(
            Conversation.tenant_id == current_user.tenant_id,
            Conversation.user_id == current_user.id,
        )
        .order_by(Conversation.updated_at.desc())
    )
    return res.scalars().all()


@router.get("/chat/conversations/{conversation_id}", response_model=ConversationDetailOut)
async def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Fetches a conversation with its full message history and citations."""
    res = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == current_user.tenant_id,
        )
    )
    conv = res.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages_res = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    conv_messages = messages_res.scalars().all()

    return ConversationDetailOut(
        id=conv.id,
        tenant_id=conv.tenant_id,
        user_id=conv.user_id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=conv_messages,
    )



@router.patch("/chat/conversations/{conversation_id}", response_model=ConversationOut)
async def patch_conversation(
    conversation_id: str,
    payload: ConversationPatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Renames or patches a conversation title."""
    res = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == current_user.tenant_id,
        )
    )
    conv = res.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if payload.title is not None:
        conv.title = payload.title[:200]

    await db.commit()
    await db.refresh(conv)
    return conv


@router.delete("/chat/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Deletes a conversation and all its messages."""
    res = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.tenant_id == current_user.tenant_id,
        )
    )
    conv = res.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await db.delete(conv)
    await db.commit()
    return {"message": "Conversation deleted"}


@router.get("/health")
async def health_check():
    """System health check endpoint."""
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV}
