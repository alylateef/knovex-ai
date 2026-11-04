"""
Knovex AI - Comparative Evaluation Benchmark
Compares Dense-Only vs Hybrid (Dense + BM25 RRF) vs Hybrid + CrossEncoder Reranking
on the Knovex AI starter corpus and synthetic evaluation benchmark.
"""

import json
import logging
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List
from qdrant_client import QdrantClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from knovex.document_loader import parse_and_chunk_document
from evaluation.metrics import (
    calculate_keyword_coverage,
    calculate_mrr,
    calculate_recall_at_k,
    verify_citation_accuracy,
)
from knovex.rag import (
    get_cross_encoder,
    get_dense_embeddings,
    get_qdrant_client,
    get_vector_store,
    run_rag_pipeline,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("eval")


def run_benchmark():
    eval_dir = Path(__file__).parent
    corpus_dir = eval_dir / "starter_corpus"
    dataset_file = eval_dir / "synthetic_eval_data.json"

    with open(dataset_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    questions = data["questions"]
    tenant_id = "eval-benchmark-tenant"

    logger.info("Initializing evaluation documents in Qdrant...")
    # Ingest corpus files for evaluation tenant
    all_chunks = []
    for file_path in corpus_dir.glob("*.txt"):
        doc_id = f"doc_{file_path.stem}"
        chunks = parse_and_chunk_document(file_path=file_path, document_id=doc_id, tenant_id=tenant_id)
        all_chunks.extend(chunks)

    # Upsert to vector store
    store = get_vector_store()
    chunk_ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, f"{c.metadata['document_id']}_{c.metadata['chunk_index']}")) for c in all_chunks]
    store.add_documents(documents=all_chunks, ids=chunk_ids)
    logger.info(f"Ingested {len(all_chunks)} evaluation chunks.")

    modes = ["hybrid_rrf", "hybrid_rerank"]
    results = {}

    for mode in modes:
        recalls_at_3 = []
        recalls_at_5 = []
        mrrs = []
        kw_coverages = []
        latencies = []

        for q in questions:
            query = q["question"]
            expected_doc = q["expected_doc_name"]
            expected_kws = q["expected_keywords"]

            start_t = time.perf_counter()
            rerank_flag = (mode == "hybrid_rerank")
            pipeline_out = run_rag_pipeline(question=query, tenant_id=tenant_id, rerank=rerank_flag)
            latency = (time.perf_counter() - start_t) * 1000

            retrieved = pipeline_out.get("reranked_docs" if rerank_flag else "retrieved_docs", [])

            recalls_at_3.append(calculate_recall_at_k(retrieved, expected_doc, k=3))
            recalls_at_5.append(calculate_recall_at_k(retrieved, expected_doc, k=5))
            mrrs.append(calculate_mrr(retrieved, expected_doc))
            kw_coverages.append(calculate_keyword_coverage(retrieved, expected_kws))
            latencies.append(latency)

        results[mode] = {
            "recall@3": sum(recalls_at_3) / len(recalls_at_3),
            "recall@5": sum(recalls_at_5) / len(recalls_at_5),
            "mrr": sum(mrrs) / len(mrrs),
            "keyword_coverage": sum(kw_coverages) / len(kw_coverages),
            "avg_latency_ms": sum(latencies) / len(latencies),
        }

    # Print summary table
    print("\n" + "=" * 70)
    print(" KNOVEX AI — RETRIEVAL & RERANKING EVALUATION RESULTS")
    print(" (Synthetic Benchmark: Unverified Ground Truth for Testing)")
    print("=" * 70)
    print(f"{'Metric':<25} | {'Hybrid (Dense+BM25)':<20} | {'Hybrid + Reranking':<20}")
    print("-" * 70)
    print(f"{'Recall@3':<25} | {results['hybrid_rrf']['recall@3']:<20.3f} | {results['hybrid_rerank']['recall@3']:<20.3f}")
    print(f"{'Recall@5':<25} | {results['hybrid_rrf']['recall@5']:<20.3f} | {results['hybrid_rerank']['recall@5']:<20.3f}")
    print(f"{'MRR':<25} | {results['hybrid_rrf']['mrr']:<20.3f} | {results['hybrid_rerank']['mrr']:<20.3f}")
    print(f"{'Keyword Coverage':<25} | {results['hybrid_rrf']['keyword_coverage']:<20.3f} | {results['hybrid_rerank']['keyword_coverage']:<20.3f}")
    print(f"{'Avg Latency (ms)':<25} | {results['hybrid_rrf']['avg_latency_ms']:<20.1f} | {results['hybrid_rerank']['avg_latency_ms']:<20.1f}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_benchmark()
