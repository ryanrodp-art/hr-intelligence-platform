import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))

import pytest
import json
import time
import httpx
import urllib.parse
from deepeval import evaluate
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
from deepeval.test_case import LLMTestCase

BACKEND_URL = "http://localhost:8000"


def get_db_response(question: str) -> dict:
    """Call /rag/db/query and return the full response dict."""
    response = httpx.post(
        f"{BACKEND_URL}/rag/db/query",
        json={"question": question},
        timeout=30,
    )
    response.raise_for_status()
    result = response.json()
    time.sleep(0.5)
    return result


def get_db_context(question: str) -> list[str]:
    """
    For database RAG, retrieval_context is the SQL result
    formatted as text — what ARIA had access to when answering.
    We reconstruct this by calling the executor directly.
    """
    from rag.database_rag.nl_to_sql import generate_validated_sql
    from rag.database_rag.executor import execute_query, format_results_for_llm
    import asyncio

    sql, is_valid, error = asyncio.run(generate_validated_sql(question))
    if not is_valid:
        return ["No database results available"]

    result = execute_query(sql)
    formatted = format_results_for_llm(result)
    time.sleep(0.5)
    return [formatted]


@pytest.fixture(scope="module")
def db_golden_set() -> list[dict]:
    golden_set_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "datasets", "database_rag_golden_set.json",
    )
    with open(golden_set_path) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def db_metrics() -> dict:
    return {
        "faithfulness": FaithfulnessMetric(
            threshold=0.8,
            model="gpt-4o",
        ),
        "answer_relevancy": AnswerRelevancyMetric(
            threshold=0.7,
            model="gpt-4o",
        ),
    }


def test_db_employee_lookup(db_golden_set, db_metrics):
    """Employee name lookups must return accurate factual answers."""
    lookup_entries = [e for e in db_golden_set if e["query_type"] == "employee_lookup"][:3]
    test_cases = []
    for item in lookup_entries:
        result = get_db_response(item["input"])
        context = get_db_context(item["input"])
        test_cases.append(LLMTestCase(
            input=item["input"],
            actual_output=result["answer"],
            expected_output=item["expected_output"],
            retrieval_context=context,
        ))
    results = evaluate(
        test_cases=test_cases,
        metrics=[db_metrics["faithfulness"], db_metrics["answer_relevancy"]],
    )
    assert all(r.success for r in results.test_results), (
        "One or more employee lookup answers failed faithfulness or relevancy"
    )


def test_db_aggregate_queries(db_golden_set, db_metrics):
    """Aggregate queries must return accurate counts and summaries."""
    agg_entries = [e for e in db_golden_set if e["query_type"] == "aggregate"][:3]
    test_cases = []
    for item in agg_entries:
        result = get_db_response(item["input"])
        context = get_db_context(item["input"])
        test_cases.append(LLMTestCase(
            input=item["input"],
            actual_output=result["answer"],
            expected_output=item["expected_output"],
            retrieval_context=context,
        ))
    results = evaluate(
        test_cases=test_cases,
        metrics=[db_metrics["faithfulness"], db_metrics["answer_relevancy"]],
    )
    assert all(r.success for r in results.test_results), (
        "One or more aggregate query answers failed faithfulness or relevancy"
    )


def test_db_join_queries(db_golden_set, db_metrics):
    """JOIN queries across tables must return complete accurate results."""
    join_entries = [e for e in db_golden_set if e["query_type"] == "join"]
    test_cases = []
    for item in join_entries:
        result = get_db_response(item["input"])
        context = get_db_context(item["input"])
        test_cases.append(LLMTestCase(
            input=item["input"],
            actual_output=result["answer"],
            expected_output=item["expected_output"],
            retrieval_context=context,
        ))
    results = evaluate(
        test_cases=test_cases,
        metrics=[db_metrics["faithfulness"], db_metrics["answer_relevancy"]],
    )
    assert all(r.success for r in results.test_results), (
        "One or more JOIN query answers failed faithfulness or relevancy"
    )


def test_db_routing_boundary(db_golden_set):
    """
    Database questions must route to 'db'.
    Policy questions must route to 'rag'.
    No LLM judge — pure assertion.
    """
    db_questions = [e["input"] for e in db_golden_set]
    policy_questions = [
        "What is the parental leave policy?",
        "How do I report a harassment complaint?",
        "What is the remote work policy?",
    ]

    failures = []

    for question in db_questions:
        encoded = urllib.parse.quote(question)
        response = httpx.get(
            f"{BACKEND_URL}/rag/classify?query={encoded}",
            timeout=10,
        )
        response.raise_for_status()
        classification = response.json().get("classification")
        if classification != "db":
            failures.append(
                f"Expected 'db' for: {question[:50]} → got '{classification}'"
            )

    for question in policy_questions:
        encoded = urllib.parse.quote(question)
        response = httpx.get(
            f"{BACKEND_URL}/rag/classify?query={encoded}",
            timeout=10,
        )
        response.raise_for_status()
        classification = response.json().get("classification")
        if classification != "rag":
            failures.append(
                f"Expected 'rag' for: {question[:50]} → got '{classification}'"
            )

    assert not failures, "\n".join(failures)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
