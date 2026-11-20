"""
Knovex AI - Unit Tests for LangGraph Workflow & Citation Validation
"""

import pytest
from langchain_core.documents import Document
from knovex.rag import (
    assess_evidence_node,
    decline_to_answer_node,
    generate_answer_node,
    should_generate,
)
from evaluation.metrics import verify_citation_accuracy


def test_evidence_assessment_sufficient():
    state = {
        "question": "What is Knovex AI?",
        "reranked_docs": [
            Document(page_content="Knovex AI is an enterprise RAG system with multi-tenant isolation.", metadata={})
        ],
    }
    res = assess_evidence_node(state)
    assert res["evidence_status"] == "sufficient"
    assert should_generate(res) == "generate_answer"


def test_evidence_assessment_insufficient_empty():
    state = {
        "question": "What is Knovex AI?",
        "reranked_docs": [],
    }
    res = assess_evidence_node(state)
    assert res["evidence_status"] == "insufficient"
    assert should_generate(res) == "decline_to_answer"


def test_decline_to_answer_node():
    state = {"question": "What is the secret formula?"}
    res = decline_to_answer_node(state)
    # Message says "not sufficient information" — check for "sufficient" keyword
    assert "sufficient" in res["answer"].lower()
    assert res["evidence_status"] == "insufficient"
    assert res["citations"] == []


def test_citation_accuracy_verification():
    retrieved_docs = [
        Document(page_content="Content 1", metadata={"source": "spec.txt", "page": 2}),
        Document(page_content="Content 2", metadata={"source": "policy.txt", "page": 1}),
    ]

    valid_citations = [
        {"filename": "spec.txt", "page_number": 2, "snippet": "Content 1"},
        {"filename": "policy.txt", "page_number": 1, "snippet": "Content 2"},
    ]
    invalid_citations = [
        {"filename": "fabricated_file.txt", "page_number": 99, "snippet": "Fake"},
    ]

    assert verify_citation_accuracy(valid_citations, retrieved_docs) == 1.0
    assert verify_citation_accuracy(invalid_citations, retrieved_docs) == 0.0


def test_cross_lingual_query_detection():
    from knovex.rag import is_non_english_query, normalize_search_query

    # English queries should return False immediately (0ms overhead)
    assert not is_non_english_query("What happens if an employee is absent for three consecutive days?")
    assert not is_non_english_query("What does a 2.5 kg Overnight parcel cost, including fuel surcharge?")
    assert not is_non_english_query("Knovex AI multi-tenant isolation")

    # Roman Urdu / Hindi queries should return True
    assert is_non_english_query("Agar koi bina bataye teen din office na aaye to kya hota hai?")
    assert is_non_english_query("overnight parcel ka rate kitna hai?")
    assert is_non_english_query("mujhe batao company ki leave policy kya hai")

    # English normalization fallback / bypass check
    english_q = "What is the refund timeline?"
    assert normalize_search_query(english_q) == english_q
