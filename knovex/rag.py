"""
Knovex AI - RAG Pipeline Engine
Orchestrates Qdrant hybrid retrieval, CrossEncoder reranking,
evidence evaluation, and streaming generation via LangGraph.
"""

from functools import lru_cache
import logging
import os
from typing import Any, Dict, List, Optional, Tuple, TypedDict
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from knovex.config import get_settings
from knovex.observability import get_langsmith_config

logger = logging.getLogger(__name__)
settings = get_settings()

# Model and cache configuration
os.environ["HF_HOME"] = str(settings.HF_HOME)
os.environ["SENTENCE_TRANSFORMERS_HOME"] = str(settings.HF_HOME)
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
if settings.HUGGINGFACE_API_KEY:
    os.environ["HF_TOKEN"] = settings.HUGGINGFACE_API_KEY
    os.environ["HUGGINGFACEHUB_API_TOKEN"] = settings.HUGGINGFACE_API_KEY


@lru_cache(maxsize=1)
def get_dense_embeddings():
    """Lazily load HuggingFaceEmbeddings once and cache in memory."""
    from langchain_huggingface import HuggingFaceEmbeddings
    logger.info(f"Loading dense embedding: {settings.DENSE_MODEL_NAME}")
    model_kwargs = {"device": "cpu"}
    if settings.HUGGINGFACE_API_KEY:
        model_kwargs["token"] = settings.HUGGINGFACE_API_KEY
    return HuggingFaceEmbeddings(
        model_name=settings.DENSE_MODEL_NAME,
        cache_folder=str(settings.HF_HOME),
        model_kwargs=model_kwargs,
        encode_kwargs={"normalize_embeddings": True, "batch_size": 64},
    )


@lru_cache(maxsize=1)
def get_sparse_embeddings():
    """Lazily load FastEmbedSparse once and cache in memory."""
    from langchain_qdrant import FastEmbedSparse
    logger.info(f"Loading sparse BM25: {settings.SPARSE_MODEL_NAME}")
    return FastEmbedSparse(
        model_name=settings.SPARSE_MODEL_NAME,
        cache_dir=str(settings.FASTEMBED_CACHE_DIR),
    )


@lru_cache(maxsize=1)
def get_cross_encoder():
    """Lazily load CrossEncoder once and cache in memory."""
    from sentence_transformers import CrossEncoder
    logger.info(f"Loading CrossEncoder: {settings.RERANKER_MODEL_NAME}")
    return CrossEncoder(
        settings.RERANKER_MODEL_NAME,
        cache_folder=str(settings.HF_HOME),
        max_length=512,
    )


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    """Connect to Qdrant client once and cache connection."""
    logger.info(f"Connecting to Qdrant at {settings.QDRANT_URL}")
    if settings.QDRANT_URL.startswith("http://") or settings.QDRANT_URL.startswith("https://"):
        return QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY if settings.QDRANT_API_KEY else None,
            timeout=10.0,
        )
    return QdrantClient(path=settings.QDRANT_URL)


@lru_cache(maxsize=1)
def get_vector_store():
    """Returns a cached QdrantVectorStore with native hybrid (Dense + BM25) search."""
    from langchain_qdrant import QdrantVectorStore, RetrievalMode

    client = get_qdrant_client()
    col_name = settings.QDRANT_COLLECTION_NAME

    try:
        cols = [c.name for c in client.get_collections().collections]
        if col_name not in cols:
            client.create_collection(
                collection_name=col_name,
                vectors_config={"dense": qmodels.VectorParams(size=384, distance=qmodels.Distance.COSINE)},
                sparse_vectors_config={"sparse": qmodels.SparseVectorParams(modifier=qmodels.Modifier.IDF)},
            )
            client.create_payload_index(
                collection_name=col_name,
                field_name="metadata.tenant_id",
                field_schema=qmodels.PayloadSchemaType.KEYWORD,
            )
    except Exception as e:
        logger.warning(f"Qdrant collection check: {e}")

    return QdrantVectorStore(
        client=client,
        collection_name=col_name,
        embedding=get_dense_embeddings(),
        sparse_embedding=get_sparse_embeddings(),
        retrieval_mode=RetrievalMode.HYBRID,
        vector_name="dense",
        sparse_vector_name="sparse",
    )



# ---------------------------------------------------------
# LangGraph Workflow State & Nodes
# ---------------------------------------------------------

class RAGState(TypedDict):
    question: str
    tenant_id: str
    rerank: bool
    retrieved_docs: List[Document]
    reranked_docs: List[Document]
    evidence_status: str  # "sufficient" | "insufficient"
    answer: str
    citations: List[Dict[str, Any]]


def retrieve_node(state: RAGState) -> Dict[str, Any]:
    """Node 1: Tenant-isolated hybrid retrieval via LangChain VectorStoreRetriever."""
    tenant_id = state["tenant_id"]
    query = state["question"]
    store = get_vector_store()

    retriever = store.as_retriever(
        search_kwargs={
            "k": settings.RETRIEVAL_CANDIDATE_LIMIT,
            "filter": qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="metadata.tenant_id",
                        match=qmodels.MatchValue(value=tenant_id),
                    )
                ]
            ),
        }
    )

    try:
        docs = retriever.invoke(query)
    except Exception as e:
        logger.error(f"Error during LangChain retrieval: {e}")
        docs = []

    return {"retrieved_docs": docs}


def rerank_node(state: RAGState) -> Dict[str, Any]:
    """
    Node 2: CrossEncoder reranking.
    Scores all retrieved candidates with the CrossEncoder for maximum semantic accuracy,
    selects top K chunks by relevance score, and sorts them in document order for coherent context flow.
    """
    import time
    docs = state.get("retrieved_docs", [])
    if not docs:
        return {"reranked_docs": []}

    top_docs: List[Document] = []
    if state.get("rerank", True):
        try:
            query = state["question"]
            encoder = get_cross_encoder()
            # Pass full chunk content so CrossEncoder scores the entire text accurately
            pairs = [[query, doc.page_content] for doc in docs]
            t0 = time.perf_counter()
            scores = encoder.predict(pairs, show_progress_bar=False)
            logger.info(f"CrossEncoder scored {len(pairs)} pairs in {time.perf_counter()-t0:.2f}s")

            doc_scores = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
            for doc, score in doc_scores:
                doc.metadata["rerank_score"] = float(score)
                top_docs.append(doc)
        except Exception as e:
            logger.warning(f"Reranking failed or skipped: {e}")
            top_docs = list(docs)
    else:
        top_docs = list(docs)

    # Take the top K highest-scoring chunks
    selected_docs = top_docs[: settings.RERANKER_TOP_K]

    # Sort selected chunks in original document order for uninterrupted context reading
    selected_docs.sort(
        key=lambda d: (
            str(d.metadata.get("source", "")),
            int(d.metadata.get("page", 0)),
            int(d.metadata.get("chunk_index", 0)),
        )
    )

    return {"reranked_docs": selected_docs}




SYSTEM_PROMPT = (
    "You are Knovex AI, a highly accurate, grounded document assistant.\n\n"
    "Instructions:\n"
    "1. Accuracy: Base your answer strictly on the provided Retrieved Context. Never assume, extrapolate, or invent facts not stated.\n"
    "2. Source Separation: If cited chunks come from different documents, plans or versions, answer for each source separately and never compare or combine numbers across them.\n"
    "3. Logical Precision: Preserve logical connectors and quantifiers exactly as in the source (and/or/unless/except, all/any/only). Do not add 'only' or 'all' unless the source explicitly says so.\n"
    "4. Missing Information: Only state that information is not available if the context is completely silent on the topic. If partial facts exist, state them accurately.\n"
    "5. Formatting & Conciseness: Be concise: no tables unless the user explicitly asks, maximum 6 sentences otherwise.\n"
    "6. Citations: Cite your sources using bracketed numbers like [1], [2] corresponding directly to the numbered context blocks used."
)


def format_context(docs: List[Document]) -> Tuple[str, Dict[int, Dict[str, Any]]]:
    """Formats retrieved document chunks into numbered context blocks and extracts citation metadata."""
    context_parts = []
    metadata_by_index: Dict[int, Dict[str, Any]] = {}
    for i, doc in enumerate(docs, start=1):
        meta = doc.metadata
        src = meta.get("source", "Unknown Document")
        pg = meta.get("page", 1)
        doc_id = meta.get("document_id", "")
        chunk_idx = meta.get("chunk_index", 0)

        context_parts.append(f"[{i}] Document: {src} (Page {pg})\n{doc.page_content}")
        metadata_by_index[i] = {
            "document_id": doc_id,
            "filename": src,
            "page_number": pg,
            "chunk_index": chunk_idx,
            "snippet": doc.page_content[:200] + ("..." if len(doc.page_content) > 200 else ""),
            "relevance_score": meta.get("rerank_score", 1.0),
            "validated": True,
        }
    return "\n\n".join(context_parts), metadata_by_index


def extract_citations(answer: str, metadata_by_index: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extracts [1], [2] citation indices from generated text and maps to chunk metadata."""
    import re
    used_indices = set(int(m) for m in re.findall(r"\[(\d+)\]", answer) if int(m) in metadata_by_index)
    if used_indices:
        return [metadata_by_index[idx] for idx in sorted(used_indices)]
    return [metadata_by_index[idx] for idx in sorted(metadata_by_index.keys())[:3]]


def get_chat_llm():
    """Initializes the configured LLM instance (Groq or xAI)."""
    if settings.GROQ_API_KEY and settings.GROQ_API_KEY.strip() and not settings.GROQ_API_KEY.startswith("gsk-your"):
        try:
            from langchain_groq import ChatGroq
            return ChatGroq(
                groq_api_key=settings.GROQ_API_KEY,
                model_name=settings.GROQ_MODEL,
                temperature=settings.GROK_TEMPERATURE,
                max_tokens=settings.GROK_MAX_TOKENS,
            )
        except Exception as e:
            logger.error(f"Failed to initialize ChatGroq: {e}")

    if settings.XAI_API_KEY and settings.XAI_API_KEY.strip() and not settings.XAI_API_KEY.startswith("xai-your"):
        try:
            from langchain_xai import ChatXAI
            return ChatXAI(
                xai_api_key=settings.XAI_API_KEY,
                model=settings.GROK_MODEL,
                temperature=settings.GROK_TEMPERATURE,
                max_tokens=settings.GROK_MAX_TOKENS,
            )
        except Exception as e:
            logger.error(f"Failed to initialize ChatXAI: {e}")
    return None


def assess_evidence_node(state: RAGState) -> Dict[str, Any]:
    """Node 3: Assess if retrieved documents contain sufficient evidence."""
    docs = state.get("reranked_docs", [])
    if not docs:
        return {"evidence_status": "insufficient"}

    combined_len = sum(len(d.page_content.strip()) for d in docs)
    if combined_len < 30:
        return {"evidence_status": "insufficient"}

    return {"evidence_status": "sufficient"}


def should_generate(state: RAGState) -> str:
    """Conditional edge: Route to answer generation or polite refusal."""
    if state.get("evidence_status") == "sufficient":
        return "generate_answer"
    return "decline_to_answer"


def generate_answer_node(state: RAGState) -> Dict[str, Any]:
    """Node 4: Call LLM with strict grounding prompt and mapped citations [1], [2]."""
    query = state["question"]
    docs = state.get("reranked_docs", [])
    context_str, metadata_by_index = format_context(docs)
    user_prompt = f"Retrieved Context:\n{context_str}\n\nQuestion: {query}\n\nAnswer:"
    llm = get_chat_llm()

    if llm is not None:
        try:
            response = llm.invoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ])
            answer = response.content
        except Exception as e:
            logger.error(f"LLM API invocation error: {e}")
            answer = f"Error communicating with LLM API: {str(e)}. Retrieved {len(docs)} relevant context chunks."
    else:
        if docs:
            answer = (
                f"Based on the retrieved context [1]:\n\n"
                f"{docs[0].page_content[:300]}...\n\n"
                f"[1]\n\n"
                f"*(Note: Add GROQ_API_KEY or XAI_API_KEY in .env to enable live LLM generation)*"
            )
        else:
            answer = "No LLM API key configured. Add GROQ_API_KEY in .env to enable live LLM generation."

    citations = list(metadata_by_index.values())
    return {"answer": answer, "citations": citations}


def decline_to_answer_node(state: RAGState) -> Dict[str, Any]:
    """Node 5: Grounded refusal when evidence is insufficient."""
    return {
        "answer": "I do not have sufficient information in the uploaded tenant documents to answer your question accurately.",
        "citations": [],
        "evidence_status": "insufficient",
    }


def build_rag_graph() -> Any:
    """Builds and compiles the LangGraph StateGraph workflow."""
    workflow = StateGraph(RAGState)

    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("rerank", rerank_node)
    workflow.add_node("assess_evidence", assess_evidence_node)
    workflow.add_node("generate_answer", generate_answer_node)
    workflow.add_node("decline_to_answer", decline_to_answer_node)

    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "rerank")
    workflow.add_edge("rerank", "assess_evidence")
    workflow.add_conditional_edges(
        "assess_evidence",
        should_generate,
        {
            "generate_answer": "generate_answer",
            "decline_to_answer": "decline_to_answer",
        },
    )
    workflow.add_edge("generate_answer", END)
    workflow.add_edge("decline_to_answer", END)

    return workflow.compile()


@lru_cache(maxsize=1)
def get_rag_graph():
    """Lazily compile and cache the LangGraph StateGraph workflow."""
    return build_rag_graph()


def run_rag_pipeline(question: str, tenant_id: str, rerank: bool = True) -> Dict[str, Any]:
    """Synchronous/convenience wrapper to run the LangGraph RAG pipeline."""
    initial_state: RAGState = {
        "question": question,
        "tenant_id": tenant_id,
        "rerank": rerank,
        "retrieved_docs": [],
        "reranked_docs": [],
        "evidence_status": "insufficient",
        "answer": "",
        "citations": [],
    }
    graph = get_rag_graph()
    run_config = get_langsmith_config(
        tenant_id=tenant_id,
        run_name=f"knovex_rag_{tenant_id[:8]}",
        mode="sync",
        extra_metadata={"rerank": rerank},
    )
    result = graph.invoke(initial_state, config=run_config)
    return result


def stream_rag_pipeline(question: str, tenant_id: str, rerank: bool = True):
    """
    Generator that performs retrieval & reranking, yields initial metadata/citations,
    streams LLM tokens in real-time, and yields the final complete response.
    """
    import time

    # 1. Retrieve candidates via hybrid search
    t_ret_start = time.perf_counter()
    retrieve_res = retrieve_node({"tenant_id": tenant_id, "question": question})
    docs = retrieve_res.get("retrieved_docs", [])
    retrieval_ms = max(1, int((time.perf_counter() - t_ret_start) * 1000))

    # 2. CrossEncoder Rerank
    t_rerank_start = time.perf_counter()
    rerank_res = rerank_node({"tenant_id": tenant_id, "question": question, "rerank": rerank, "retrieved_docs": docs})
    reranked_docs = rerank_res.get("reranked_docs", [])
    rerank_ms = max(1, int((time.perf_counter() - t_rerank_start) * 1000)) if rerank else 0

    server_timings = {
        "retrieval_ms": retrieval_ms,
        "rerank_ms": rerank_ms,
    }

    # 3. Assess evidence
    evidence_res = assess_evidence_node({"reranked_docs": reranked_docs})
    evidence_status = evidence_res.get("evidence_status", "insufficient")

    if evidence_status != "sufficient" or not reranked_docs:
        decline_res = decline_to_answer_node({})
        yield {
            "type": "metadata",
            "citations": [],
            "evidence_status": "insufficient",
            "server_timings": server_timings,
        }
        yield {"type": "delta", "content": decline_res["answer"]}
        yield {"type": "done", "answer": decline_res["answer"], "citations": [], "evidence_status": "insufficient"}
        return

    # 4. Format context blocks and yield initial metadata
    context_str, metadata_by_index = format_context(reranked_docs)
    yield {
        "type": "metadata",
        "citations": list(metadata_by_index.values()),
        "evidence_status": "sufficient",
        "server_timings": server_timings,
    }

    user_prompt = f"Retrieved Context:\n{context_str}\n\nQuestion: {question}\n\nAnswer:"
    llm = get_chat_llm()

    full_answer_parts = []
    if llm is not None:
        try:
            stream_config = get_langsmith_config(
                tenant_id=tenant_id,
                run_name=f"knovex_stream_{tenant_id[:8]}",
                mode="streaming",
                extra_metadata={"evidence_status": "sufficient"},
            )
            for chunk in llm.stream(
                [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=user_prompt),
                ],
                config=stream_config,
            ):
                token = chunk.content
                if token:
                    full_answer_parts.append(token)
                    yield {"type": "delta", "content": token}
        except Exception as e:
            err_msg = f"\n\n[Error communicating with LLM API: {e}]"
            full_answer_parts.append(err_msg)
            yield {"type": "delta", "content": err_msg}
    else:
        fallback = f"Based on retrieved context [1]:\n\n{reranked_docs[0].page_content[:300]}...\n\n[1]"
        full_answer_parts.append(fallback)
        yield {"type": "delta", "content": fallback}

    full_answer = "".join(full_answer_parts)
    citations = list(metadata_by_index.values())

    yield {
        "type": "done",
        "answer": full_answer,
        "citations": citations,
        "evidence_status": "sufficient",
    }

