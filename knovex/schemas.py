from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------------------------------------------------------
# Auth & User Schemas
# ---------------------------------------------------------

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user_id: str
    tenant_id: str
    role: str
    email: str


class TokenData(BaseModel):
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)


class RegisterRequest(BaseModel):
    organization_name: str = Field(..., min_length=2, max_length=128)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(default="", max_length=128)
    role: Optional[str] = Field(default="admin", pattern="^(admin|user)$")


class JoinRequest(BaseModel):
    org_code: str = Field(..., min_length=2, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str = Field(default="", max_length=128)
    role: Optional[str] = Field(default="user", pattern="^(admin|user)$")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    organization_name: Optional[str] = ""
    org_code: Optional[str] = ""


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    is_active: bool
    created_at: datetime


# ---------------------------------------------------------
# Document & Ingestion Schemas
# ---------------------------------------------------------

class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    filename: str
    file_size: int
    mime_type: str
    total_pages: Optional[int]
    total_chunks: int
    created_at: datetime


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    job_id: str
    status: str
    message: str


class IngestionStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    tenant_id: str
    status: str
    progress_percent: int
    error_message: Optional[str] = None
    retry_count: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ---------------------------------------------------------
# Chat & RAG Schemas
# ---------------------------------------------------------

class CitationItem(BaseModel):
    document_id: str
    filename: str
    page_number: Optional[int] = 1
    chunk_index: int = 0
    snippet: str
    relevance_score: float = 0.0
    validated: bool = True


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[str] = None
    rerank: Optional[bool] = True
    temperature: Optional[float] = 0.1


class ChatMessageResponse(BaseModel):
    conversation_id: str
    message_id: str
    question: str
    answer: str
    evidence_status: str  # "sufficient" | "insufficient" | "declined"
    citations: List[CitationItem]
    retrieval_mode: str = "hybrid_rrf"
    reranked: bool = False


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str
    content: str
    citations: Optional[List[Dict[str, Any]]] = None
    evidence_status: str
    created_at: datetime


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationDetailOut(ConversationOut):
    messages: List[MessageOut] = []


class ConversationPatchRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)


# ---------------------------------------------------------
# Evaluation Schemas
# ---------------------------------------------------------

class EvalItem(BaseModel):
    question: str
    ground_truth_answer: str
    expected_doc_name: str
    expected_keywords: List[str]


class EvaluationResultOut(BaseModel):
    total_queries: int
    recall_at_k: float
    mrr: float
    citation_accuracy: float
    retrieval_mode: str
    reranker_enabled: bool
    latency_seconds_avg: float
    details: List[Dict[str, Any]]
