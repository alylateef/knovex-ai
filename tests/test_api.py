"""
Knovex AI - Integration Tests for FastAPI Endpoints & Tenant Isolation
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_auth_registration_and_login(client: AsyncClient):
    reg_payload = {
        "organization_name": "Stark Industries",
        "email": "tony@stark.com",
        "password": "IronManPassword2026!",
        "full_name": "Tony Stark",
    }
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 200
    reg_data = reg_res.json()
    assert "access_token" in reg_data
    assert reg_data["role"] == "admin"
    assert reg_data["email"] == "tony@stark.com"

    # Login with same credentials
    login_payload = {
        "email": "tony@stark.com",
        "password": "IronManPassword2026!",
    }
    login_res = await client.post("/api/v1/auth/login", json=login_payload)
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert "access_token" in login_data


@pytest.mark.asyncio
async def test_tenant_isolation_on_documents(client: AsyncClient, tenant_a, tenant_b, monkeypatch):
    # Patch the sync ingestion pipeline so it doesn't try to connect to a separate SQLite DB
    monkeypatch.setattr("knovex.api.run_ingestion_pipeline", lambda *args, **kwargs: True)

    # 1. Tenant A uploads a document
    file_content = b"Proprietary arc reactor technical specifications for Stark Industries."
    files = {"file": ("arc_reactor.txt", file_content, "text/plain")}
    headers_a = {"Authorization": f"Bearer {tenant_a['token']}"}

    upload_res = await client.post("/api/v1/documents/upload", files=files, headers=headers_a)
    assert upload_res.status_code == 200
    doc_id = upload_res.json()["document_id"]

    # 2. Tenant A lists documents -> sees arc_reactor.txt
    list_a = await client.get("/api/v1/documents", headers=headers_a)
    assert list_a.status_code == 200
    docs_a = list_a.json()
    assert len(docs_a) == 1
    assert docs_a[0]["id"] == doc_id
    assert docs_a[0]["filename"] == "arc_reactor.txt"

    # 3. Tenant B lists documents -> MUST see 0 documents (strict tenant isolation!)
    headers_b = {"Authorization": f"Bearer {tenant_b['token']}"}
    list_b = await client.get("/api/v1/documents", headers=headers_b)
    assert list_b.status_code == 200
    docs_b = list_b.json()
    assert len(docs_b) == 0, "Tenant B must not see Tenant A's documents"

    # 4. Tenant B (regular user) cannot upload documents (RBAC enforcement)
    upload_b_res = await client.post("/api/v1/documents/upload", files=files, headers=headers_b)
    assert upload_b_res.status_code == 403, "Non-admin user must be rejected from uploading documents"


@pytest.mark.asyncio
async def test_chat_query_flow(client: AsyncClient, tenant_a):
    headers = {"Authorization": f"Bearer {tenant_a['token']}"}
    chat_payload = {
        "message": "What is the status of the project?",
        "rerank": True,
    }
    res = await client.post("/api/v1/chat/query", json=chat_payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "answer" in data
    assert "conversation_id" in data
    assert "evidence_status" in data
