"""
Knovex AI - Unit Tests for Qdrant Vector Store, Tenant Isolation & CrossEncoder Reranking
"""

import uuid
import pytest
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from knovex.rag import get_cross_encoder, get_dense_embeddings, get_sparse_embeddings


def test_tenant_isolation_filter():
    client = QdrantClient(":memory:")
    col_name = "test_tenant_isolation"

    client.create_collection(
        collection_name=col_name,
        vectors_config={"dense": qmodels.VectorParams(size=384, distance=qmodels.Distance.COSINE)},
        sparse_vectors_config={"sparse": qmodels.SparseVectorParams(modifier=qmodels.Modifier.IDF)},
    )

    store = QdrantVectorStore(
        client=client,
        collection_name=col_name,
        embedding=get_dense_embeddings(),
        sparse_embedding=get_sparse_embeddings(),
        retrieval_mode=RetrievalMode.HYBRID,
        vector_name="dense",
        sparse_vector_name="sparse",
    )

    # Qdrant requires valid UUIDs as point IDs
    id_a = str(uuid.uuid4())
    id_b = str(uuid.uuid4())

    doc_a = Document(
        page_content="Confidential financial report for Acme Corp in Q3.",
        metadata={"tenant_id": "tenant-A", "document_id": "doc-a", "source": "acme_finances.txt", "page": 1, "chunk_index": 0},
    )
    doc_b = Document(
        page_content="Secret merger agreement between Beta Inc and Gamma.",
        metadata={"tenant_id": "tenant-B", "document_id": "doc-b", "source": "beta_merger.txt", "page": 1, "chunk_index": 0},
    )

    store.add_documents([doc_a, doc_b], ids=[id_a, id_b])

    # Query as Tenant A
    filter_a = qmodels.Filter(
        must=[qmodels.FieldCondition(key="metadata.tenant_id", match=qmodels.MatchValue(value="tenant-A"))]
    )
    results_a = store.similarity_search("merger agreement or financial report", k=10, filter=filter_a)

    assert len(results_a) == 1
    assert results_a[0].metadata["tenant_id"] == "tenant-A"
    assert "Acme Corp" in results_a[0].page_content
    # Tenant A MUST NOT see Tenant B's secret document
    assert not any(d.metadata["tenant_id"] == "tenant-B" for d in results_a)


def test_cross_encoder_reranker():
    encoder = get_cross_encoder()
    query = "What is the token expiration lifespan?"

    relevant_passage = "Access tokens expire after 60 minutes. Refresh tokens expire after 7 days."
    irrelevant_passage = "All upload operations are logged to the PostgreSQL database for audit."

    pairs = [[query, relevant_passage], [query, irrelevant_passage]]
    scores = encoder.predict(pairs)

    assert scores[0] > scores[1], "Relevant passage must have a higher score than irrelevant passage"
