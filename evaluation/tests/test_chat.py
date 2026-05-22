import pytest
import asyncio
import json
import os
from pathlib import Path
from deepeval import evaluate
from deepeval.metrics import GEval, AnswerRelevancyMetric, HallucinationMetric
from deepeval.test_case import LLMTestCase, SingleTurnParams
from deepeval.dataset import EvaluationDataset
import httpx

BACKEND_URL = "http://localhost:8000"
GOLDEN_SET_PATH = Path("evaluation/datasets/chat_golden_set.json")


def get_aria_response(question: str) -> str:
    """Call the ARIA chat endpoint and return the response text."""
    session_id = f"eval-session-{hash(question) & 0xFFFFFFFF}"
    response = httpx.post(
        f"{BACKEND_URL}/chat/",
        json={"message": question, "session_id": session_id},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["response"]


@pytest.fixture(scope="module")
def golden_set() -> list[dict]:
    """Load the chat golden set from disk."""
    return json.loads(GOLDEN_SET_PATH.read_text())


@pytest.fixture(scope="module")
def metrics() -> dict:
    """Instantiate the DeepEval metrics used across the test suite."""
    return {
        "role_adherence": GEval(
            name="HR Role Adherence",
            criteria="""The AI response should:
                1. Maintain the ARIA HR assistant persona throughout
                2. Only discuss HR-related topics
                3. Redirect non-HR questions back to HR topics
                4. Be professional and empathetic in tone""",
            evaluation_params=[
                SingleTurnParams.ACTUAL_OUTPUT,
                SingleTurnParams.INPUT,
            ],
            threshold=0.7,
        ),
        "answer_relevancy": AnswerRelevancyMetric(
            threshold=0.7,
            model="gpt-4o",
        ),
        "hallucination": HallucinationMetric(
            threshold=0.5,
            model="gpt-4o",
        ),
    }


def test_aria_responds_to_hr_questions(golden_set, metrics):
    """ARIA should give relevant, on-persona answers to the first 8 HR questions."""
    test_cases = []
    for item in golden_set[:8]:
        response = get_aria_response(item["input"])
        test_cases.append(
            LLMTestCase(
                input=item["input"],
                actual_output=response,
                expected_output=item["expected_output"],
            )
        )

    results = evaluate(
        test_cases=test_cases,
        metrics=[metrics["role_adherence"], metrics["answer_relevancy"]],
    )

    assert all(r.success for r in results.test_results), (
        "One or more HR question test cases failed role adherence or answer relevancy"
    )


def test_aria_rejects_non_hr_questions(golden_set, metrics):
    """ARIA should redirect the Python script question back to HR topics."""
    item = golden_set[8]  # "Can you help me write a Python script?"
    response = get_aria_response(item["input"])

    test_case = LLMTestCase(
        input=item["input"],
        actual_output=response,
        expected_output=item["expected_output"],
    )

    results = evaluate(
        test_cases=[test_case],
        metrics=[metrics["role_adherence"]],
    )

    assert all(r.success for r in results.test_results), (
        "ARIA did not redirect the non-HR question as expected"
    )


def test_aria_no_hallucination(golden_set, metrics):
    """ARIA should not hallucinate facts when answering the first 5 HR questions."""
    test_cases = []
    for item in golden_set[:5]:
        response = get_aria_response(item["input"])
        test_cases.append(
            LLMTestCase(
                input=item["input"],
                actual_output=response,
                expected_output=item["expected_output"],
                context=[],
            )
        )

    results = evaluate(
        test_cases=test_cases,
        metrics=[metrics["hallucination"]],
    )

    assert all(r.success for r in results.test_results), (
        "ARIA hallucinated in one or more responses"
    )


def test_aria_handles_sensitive_questions(golden_set, metrics):
    """ARIA should handle emotionally sensitive and legally sensitive
    questions with appropriate empathy and disclaimers."""
    # These may produce failures in Phase 1 —
    # expected to improve with RAG in Phase 3
    sensitive_indexes = [12, 14, 16, 18, 19]  # unfair treatment, multi-part leave, harassment, termination
    test_cases = []
    for i in sensitive_indexes:
        item = golden_set[i]
        response = get_aria_response(item["input"])
        test_cases.append(
            LLMTestCase(
                input=item["input"],
                actual_output=response,
                expected_output=item["expected_output"],
            )
        )

    results = evaluate(
        test_cases=test_cases,
        metrics=[metrics["role_adherence"], metrics["answer_relevancy"]],
    )

    assert all(r.success for r in results.test_results), (
        "One or more sensitive question test cases failed role adherence or answer relevancy"
    )


def test_aria_handles_knowledge_boundary_questions(golden_set, metrics):
    """ARIA should admit knowledge limits rather than hallucinate
    when asked for company-specific data it doesn't have."""
    # Tests that ARIA says 'I don't know' rather than
    # inventing specific company data
    boundary_indexes = [10, 11, 13, 15, 17]  # vague, company policy, salary, off-topic, specific vacation days
    test_cases = []
    for i in boundary_indexes:
        item = golden_set[i]
        response = get_aria_response(item["input"])
        test_cases.append(
            LLMTestCase(
                input=item["input"],
                actual_output=response,
                expected_output=item["expected_output"],
                context=[],
            )
        )

    results = evaluate(
        test_cases=test_cases,
        metrics=[metrics["hallucination"]],
    )

    assert all(r.success for r in results.test_results), (
        "ARIA hallucinated company-specific data it should not have access to"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
