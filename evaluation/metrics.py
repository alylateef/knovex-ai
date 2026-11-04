"""
Knovex AI - Evaluation Metrics
Implements Recall@K, MRR (Mean Reciprocal Rank), Keyword Coverage, and Citation Accuracy.
"""

from typing import Any, Dict, List
from langchain_core.documents import Document


def calculate_recall_at_k(retrieved_docs: List[Document], expected_doc_name: str, k: int = 5) -> float:
    """
    Computes Recall@K: 1.0 if the expected document is present in the top-K retrieved docs, else 0.0.
    """
    top_k = retrieved_docs[:k]
    for doc in top_k:
        source = doc.metadata.get("source", "")
        if expected_doc_name.lower() in source.lower():
            return 1.0
    return 0.0


def calculate_mrr(retrieved_docs: List[Document], expected_doc_name: str) -> float:
    """
    Computes Reciprocal Rank (RR): 1/rank of the first relevant document.
    Returns 0.0 if not found.
    """
    for rank, doc in enumerate(retrieved_docs, start=1):
        source = doc.metadata.get("source", "")
        if expected_doc_name.lower() in source.lower():
            return 1.0 / rank
    return 0.0


def calculate_keyword_coverage(retrieved_docs: List[Document], expected_keywords: List[str]) -> float:
    """
    Measures the proportion of expected target keywords present in the retrieved passages.
    """
    if not expected_keywords:
        return 1.0
    combined_text = " ".join(d.page_content.lower() for d in retrieved_docs)
    matched = sum(1 for kw in expected_keywords if kw.lower() in combined_text)
    return matched / len(expected_keywords)


def verify_citation_accuracy(citations: List[Dict[str, Any]], retrieved_docs: List[Document]) -> float:
    """
    Verifies that generated citations genuinely correspond to the retrieved document passages.
    Returns accuracy ratio (0.0 to 1.0).
    """
    if not citations:
        return 1.0

    retrieved_sources = {(d.metadata.get("source", ""), d.metadata.get("page", 1)) for d in retrieved_docs}
    valid_citations = 0

    for c in citations:
        c_src = c.get("filename", "")
        c_pg = c.get("page_number", 1)
        # Check if this source/page is in retrieved set
        if any(c_src.lower() in r_src.lower() and c_pg == r_pg for r_src, r_pg in retrieved_sources):
            valid_citations += 1

    return valid_citations / len(citations)
