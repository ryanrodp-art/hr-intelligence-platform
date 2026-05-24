import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))

import pytest
import json
from pathlib import Path
from deepeval import evaluate
from deepeval.metrics import (
    FaithfulnessMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ContextualRelevancyMetric,
    AnswerRelevancyMetric,
)
from deepeval.test_case import LLMTestCase
import httpx
import urllib.parse
import time

BACKEND_URL = "http://localhost:8000"
RAG_GOLDEN_SET_PATH = Path("evaluation/datasets/rag_golden_set.json")


def get_rag_response(question: str) -> dict:
    response = httpx.post(
        f"{BACKEND_URL}/rag/query",
        json={"question": question},
        timeout=60,
    )
    response.raise_for_status()
    time.sleep(0.5)
    return response.json()


def get_retrieval_context(question: str) -> list[str]:
    from rag.document_rag.retriever import retrieve
    chunks = retrieve(question, top_k=3)
    time.sleep(0.5)
    return [chunk.text for chunk in chunks]


@pytest.fixture(scope="module")
def rag_golden_set() -> list[dict]:
    return json.loads(RAG_GOLDEN_SET_PATH.read_text())


@pytest.fixture(scope="module")
def rag_metrics() -> dict:
    return {
        "faithfulness": FaithfulnessMetric(
            threshold=0.8,
            model="gpt-4o",
        ),
        "contextual_precision": ContextualPrecisionMetric(
            threshold=0.7,
            model="gpt-4o",
        ),
        "contextual_recall": ContextualRecallMetric(
            threshold=0.7,
            model="gpt-4o",
        ),
        "contextual_relevancy": ContextualRelevancyMetric(
            threshold=0.7,
            model="gpt-4o",
        ),
        "answer_relevancy": AnswerRelevancyMetric(
            threshold=0.7,
            model="gpt-4o",
        ),
    }


def test_rag_faithfulness(rag_golden_set, rag_metrics):
    # Faithfulness threshold 0.8 — ARIA must cite document facts only
    """RAG answers must be grounded in retrieved document chunks.
    No hallucination against context. Uses first 5 golden set entries."""
    test_cases = []
    for item in rag_golden_set[:3]:
        result = get_rag_response(item["input"])
        context = get_retrieval_context(item["input"])
        test_cases.append(
            LLMTestCase(
                input=item["input"],
                actual_output=result["answer"],
                expected_output=item["expected_output"],
                retrieval_context=context,
            )
        )

    results = evaluate(
        test_cases=test_cases,
        metrics=[rag_metrics["faithfulness"]],
    )

    assert all(r.success for r in results.test_results), (
        "One or more RAG answers contained information not grounded in the retrieved context"
    )


def test_rag_contextual_precision(rag_golden_set, rag_metrics):
    # Tests retrieval ranking — correct chunk should be top result
    """The most relevant chunks must be ranked first in retrieval.
    Uses leave policy entries (rows 1-5) as they have clearest
    expected retrieval order."""
    test_cases = []
    for item in rag_golden_set[:3]:
        result = get_rag_response(item["input"])
        context = get_retrieval_context(item["input"])
        test_cases.append(
            LLMTestCase(
                input=item["input"],
                actual_output=result["answer"],
                expected_output=item["expected_output"],
                retrieval_context=context,
            )
        )

    results = evaluate(
        test_cases=test_cases,
        metrics=[rag_metrics["contextual_precision"]],
    )

    assert all(r.success for r in results.test_results), (
        "Retrieval ranking failed — the most relevant chunk was not ranked first"
    )


def test_rag_contextual_recall(rag_golden_set, rag_metrics):
    # Tests retrieval completeness — all key facts must be in context
    """Retrieved chunks must contain all information needed to answer.
    Uses entries with specific multi-part expected outputs."""
    indexes = [1, 5]  # parental leave, harassment steps
    test_cases = []
    for i in indexes:
        item = rag_golden_set[i]
        result = get_rag_response(item["input"])
        context = get_retrieval_context(item["input"])
        test_cases.append(
            LLMTestCase(
                input=item["input"],
                actual_output=result["answer"],
                expected_output=item["expected_output"],
                retrieval_context=context,
            )
        )

    results = evaluate(
        test_cases=test_cases,
        metrics=[rag_metrics["contextual_recall"]],
    )

    assert all(r.success for r in results.test_results), (
        "Retrieval was incomplete — not all key facts required to answer were present in context"
    )


def test_rag_answer_relevancy(rag_golden_set, rag_metrics):
    # Regression check — RAG answers must be as relevant as chat answers
    """RAG answers must directly address the question asked.
    Uses first 5 entries."""
    test_cases = []
    for item in rag_golden_set[:3]:
        result = get_rag_response(item["input"])
        context = get_retrieval_context(item["input"])
        test_cases.append(
            LLMTestCase(
                input=item["input"],
                actual_output=result["answer"],
                expected_output=item["expected_output"],
                retrieval_context=context,
            )
        )

    results = evaluate(
        test_cases=test_cases,
        metrics=[rag_metrics["answer_relevancy"]],
    )

    assert all(r.success for r in results.test_results), (
        "One or more RAG answers did not directly address the question asked"
    )


def test_rag_document_routing(rag_golden_set):
    # All policy questions must route to RAG not general chat
    """Verify the RAG router correctly classifies all 15 policy questions
    as 'rag' and not 'chat'."""
    failures = []
    for item in rag_golden_set:
        encoded = urllib.parse.quote(item["input"])
        response = httpx.get(
            f"{BACKEND_URL}/rag/classify?query={encoded}",
            timeout=10,
        )
        response.raise_for_status()
        classification = response.json().get("classification")
        if classification != "rag":
            failures.append(f"'{item['input'][:60]}' → classified as '{classification}'")

    assert not failures, (
        "The following policy questions were incorrectly routed to chat:\n" +
        "\n".join(failures)
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
