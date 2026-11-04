# Knovex AI : Enterprise Multi-Tenant RAG Document Chatbot

> **AI Engineering Project** : Production-grade RAG with Grok (xAI), Qdrant Hybrid Search, LangGraph, CrossEncoder Reranking and multi-tenant isolation.

---

## Architecture

```
User (Browser)
    │
    ▼
FastAPI (Auth, Documents, Chat)
    │           │              │
    ▼           ▼              ▼
PostgreSQL   Qdrant        Redis
(Users,      (Dense        (JWT Revocation,
 Docs,        + BM25        Rate Limiting,
 Chunks,      Hybrid        Celery Broker)
 Messages)    Vectors
              + RRF)
    │
    ▼
LangGraph RAG Pipeline
  retrieve → rerank → assess_evidence → generate_answer | decline
    │            │
Qdrant Hybrid  CrossEncoder (ms-marco-MiniLM-L-6-v2)
   (RRF)
    │
    ▼
Grok (ChatXAI / grok-2-latest)
```

### Key Design Decisions
- **Hybrid Retrieval**: Dense (`all-MiniLM-L6-v2`, 384-dim Cosine) + Sparse (`Qdrant/bm25` via FastEmbed) fused with native Qdrant RRF
- **Tenant Isolation**: Every DB query and Qdrant search is filtered by `tenant_id` server-side only, never trusted from client
- **Grounded Generation**: Grok is given ONLY retrieved chunks as context. Declines to answer when evidence is insufficient
- **Async Ingestion**: Celery + Redis; idempotent with UUID5 point IDs; retries with backoff; status tracked in PostgreSQL

---

## Project Structure

```
D:\knovex-ai\
├── knovex/
│   ├── __init__.py
│   ├── config.py          # Pydantic Settings v2 — all configuration
│   ├── database.py        # SQLAlchemy 2 async + sync engines
│   ├── models.py          # ORM models (Tenant, User, Document, Conversation, Message…)
│   ├── schemas.py         # Pydantic v2 request/response schemas
│   ├── security.py        # JWT, bcrypt hashing, Redis revocation, rate limiting
│   ├── storage.py         # File upload with path-traversal protection
│   ├── document_loader.py # pypdf + RecursiveCharacterTextSplitter → LangChain Documents
│   ├── rag.py             # Vector store, embeddings, CrossEncoder, LangGraph workflow
│   ├── tasks.py           # Celery ingestion task (async, idempotent, retryable)
│   ├── api.py             # All FastAPI endpoints (auth, documents, chat, health)
│   ├── main.py            # FastAPI app entry point + lifespan
│   └── static/            # Vanilla HTML/CSS/JS frontend
│       ├── index.html
│       ├── styles.css
│       └── app.js
├── alembic/               # Database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial_schema.py
├── evaluation/
│   ├── metrics.py             # Recall@K, MRR, keyword coverage, citation accuracy
│   ├── run_evaluation.py      # Automated benchmark (hybrid vs hybrid+rerank)
│   ├── synthetic_eval_data.json
│   └── starter_corpus/        # Sample TXT documents for evaluation
│       ├── knovex_architecture_spec.txt
│       └── enterprise_security_policy.txt
├── tests/
│   ├── conftest.py            # Fixtures: in-memory SQLite, test client, tenant fixtures
│   ├── test_auth.py           # JWT, password hashing
│   ├── test_document_loader.py # Chunking, metadata, empty file handling
│   ├── test_vector_store.py   # Tenant isolation, CrossEncoder scoring
│   ├── test_graph.py          # LangGraph nodes, citation accuracy
│   └── test_api.py            # Auth, document upload, tenant isolation (API level)
├── requirements.txt
├── pyproject.toml
├── alembic.ini
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── .gitignore
```

---

## Quick Start (Windows PowerShell)

### Prerequisites
- Python 3.11+
- Docker Desktop (for Postgres, Redis, Qdrant)
- Git

### 1 — Clone & Set Up Environment

```powershell
# Go to project directory
cd D:\knovex-ai

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install dependencies (already done if you ran setup)
pip install -r requirements.txt
pip install greenlet email-validator
```

### 2 — Configure Environment

```powershell
# Copy example config
Copy-Item .env.example .env

# Edit .env and fill in required values:
# XAI_API_KEY=xai-your-real-key-here     ← Required for live Grok responses
# DATABASE_URL and DATABASE_SYNC_URL      ← Change password if needed
```

### 3 — Start Infrastructure (Docker)

```powershell
# Start PostgreSQL, Redis, Qdrant in background
docker-compose up postgres redis qdrant -d

# Wait ~10 seconds for services to become healthy
Start-Sleep -Seconds 10
```

### 4 — Run Database Migrations

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

### 5 — Start the API Server

```powershell
.\.venv\Scripts\python.exe -m knovex.main
# Runs at http://localhost:8000
# Frontend: http://localhost:8000/
# API Docs: http://localhost:8000/docs
```

### 6 — Start the Celery Ingestion Worker (separate terminal)

```powershell
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\celery.exe -A knovex.tasks.celery_app worker --loglevel=info --concurrency=2
```

---

## Running Tests

```powershell
.\.venv\Scripts\Activate.ps1

# Run all tests
.\.venv\Scripts\python.exe -m pytest tests -v

# Run specific test file
.\.venv\Scripts\python.exe -m pytest tests/test_auth.py -v
.\.venv\Scripts\python.exe -m pytest tests/test_vector_store.py -v
.\.venv\Scripts\python.exe -m pytest tests/test_graph.py -v
```

### What the Tests Verify

| Test File | What it Tests |
|-----------|--------------|
| `test_auth.py` | bcrypt hashing, JWT create/decode, invalid token rejection |
| `test_document_loader.py` | TXT chunking, metadata per-chunk, empty file handling |
| `test_vector_store.py` | Tenant isolation in Qdrant (in-memory), CrossEncoder score ordering |
| `test_graph.py` | LangGraph nodes (sufficient/insufficient evidence), citation accuracy |
| `test_api.py` | Register/login, document upload, tenant isolation at API level, chat flow |

> `test_vector_store.py::test_tenant_isolation_filter` downloads `all-MiniLM-L6-v2` and `Qdrant/bm25` from HuggingFace on first run — takes ~2 min. Models are cached afterwards.

---

## Running the Evaluation Benchmark

```powershell
# Run retrieval comparison: Hybrid RRF vs Hybrid + CrossEncoder Reranking
# Requires: Qdrant running
.\.venv\Scripts\python.exe -m evaluation.run_evaluation
```

> Synthetic dataset — **not human-verified ground truth**. Used only to compare retrieval modes.

---

## Full Docker Deployment

```powershell
# Start all services including the API and Celery worker
$env:XAI_API_KEY = "xai-your-key-here"
docker-compose up --build -d
```

---

## API Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/v1/auth/register` | — | Register org + admin user |
| `POST` | `/api/v1/auth/login` | — | Login, get JWT token |
| `POST` | `/api/v1/auth/logout` | ✓ | Revoke token in Redis |
| `GET` | `/api/v1/auth/me` | ✓ | Current user info |
| `POST` | `/api/v1/documents/upload` | ✓ | Upload PDF/TXT |
| `GET` | `/api/v1/documents` | ✓ | List tenant documents |
| `GET` | `/api/v1/documents/{id}/status` | ✓ | Ingestion job status |
| `DELETE` | `/api/v1/documents/{id}` | ✓ | Delete doc from DB + Qdrant |
| `POST` | `/api/v1/chat/query` | ✓ | RAG query with citations |
| `GET` | `/api/v1/chat/conversations` | ✓ | List conversations |
| `GET` | `/api/v1/chat/conversations/{id}` | ✓ | Conversation history |
| `GET` | `/api/v1/health` | — | Health check |

---

## What Requires Manual Setup

| Requirement | Status | Action Needed |
|------------|--------|---------------|
| `XAI_API_KEY` |  Required for live Grok | Get from [x.ai](https://x.ai/) and add to `.env` |
| PostgreSQL | Must be running | `docker-compose up postgres -d` |
| Redis |  Must be running | `docker-compose up redis -d` |
| Qdrant |  Must be running | `docker-compose up qdrant -d` |
| `HF_TOKEN` | Optional | Set to avoid HuggingFace rate limits on first model download |
| Docker Desktop |  Required | Must be running for docker-compose commands |

> When `XAI_API_KEY` is not configured, the API returns a mock answer that shows the retrieved context with a note to configure the key. All retrieval and reranking still works correctly.

---

## Security Notes
- Passwords are hashed with `bcrypt` (72-byte limit enforced)
- JWT tokens use `HS256` with configurable secret key — change `SECRET_KEY` in `.env` before production
- Tokens are revocable via Redis blocklist
- File uploads are sanitized against path traversal, limited to 15MB, PDF/TXT only
- Tenant isolation is enforced server-side on every DB query and Qdrant search
