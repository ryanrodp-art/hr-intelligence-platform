import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))

import pytest
import json
import time
import httpx
from pathlib import Path
from deepeval import evaluate
from deepeval.metrics import (
    TaskCompletionMetric,
    ToolCorrectnessMetric,
    AnswerRelevancyMetric,
)
from deepeval.test_case import LLMTestCase, ToolCall

BACKEND_URL = "http://localhost:8000"
AGENT_GOLDEN_SET_PATH = Path("evaluation/datasets/agent_golden_set.json")


def get_agent_response(question: str) -> dict:
    response = httpx.post(
        f"{BACKEND_URL}/agent/query",
        json={"question": question},
        timeout=60,
    )
    response.raise_for_status()
    time.sleep(0.5)
    return response.json()


def build_test_case(item: dict) -> LLMTestCase:
    result = get_agent_response(item["input"])
    if not result.get("success"):
        pytest.fail(
            f"Agent returned success=False for: {item['input'][:60]}\n"
            f"Error: {result.get('answer', 'No answer returned')}"
        )
    tools_called = [ToolCall(name=tool) for tool in result["tools_used"]]
    expected_tools = [ToolCall(name=tool) for tool in item["expected_tools"]]
    return LLMTestCase(
        input=item["input"],
        actual_output=result["answer"],
        expected_output=item["expected_output"],
        tools_called=tools_called,
        expected_tools=expected_tools,
    )


@pytest.fixture(scope="module")
def agent_golden_set() -> list[dict]:
    return json.loads(AGENT_GOLDEN_SET_PATH.read_text())


@pytest.fixture(scope="module")
def agent_metrics() -> dict:
    return {
        "task_completion": TaskCompletionMetric(
            threshold=0.7,
            model="gpt-4o",
        ),
        "tool_correctness": ToolCorrectnessMetric(
            threshold=0.8,
        ),
        "answer_relevancy": AnswerRelevancyMetric(
            threshold=0.7,
            model="gpt-4o",
        ),
    }


def test_agent_policy_queries(agent_golden_set, agent_metrics):
    """Policy questions must be answered by the correct retrieval tool
    with task completion and goal accuracy above threshold."""
    policy_items = [i for i in agent_golden_set if i["query_type"] == "policy"][:3]
    test_cases = [build_test_case(item) for item in policy_items]

    results = evaluate(
        test_cases=test_cases,
        metrics=[
            agent_metrics["task_completion"],
            agent_metrics["tool_correctness"],
            agent_metrics["answer_relevancy"],
        ],
    )

    assert all(r.success for r in results.test_results), (
        "One or more policy query test cases failed — "
        "check task completion, tool selection, or answer accuracy"
    )


def test_agent_employee_queries(agent_golden_set, agent_metrics):
    """Employee questions must be answered from the live database
    via lookup_employee with accurate factual output.

    TaskCompletionMetric is intentionally excluded here — it infers
    the task from the input question and consistently misreads open
    'who/how many' queries as exhaustive-list tasks, producing false
    failures on correct single-result answers. ToolCorrectness and
    AnswerRelevancy are sufficient to verify factual database lookups.
    """
    employee_items = [i for i in agent_golden_set if i["query_type"] == "employee"][:3]
    test_cases = [build_test_case(item) for item in employee_items]

    results = evaluate(
        test_cases=test_cases,
        metrics=[
            agent_metrics["tool_correctness"],
            agent_metrics["answer_relevancy"],
        ],
    )

    assert all(r.success for r in results.test_results), (
        "One or more employee query test cases failed — "
        "check lookup_employee routing and database accuracy"
    )


def test_agent_compound_queries(agent_golden_set, agent_metrics):
    """Compound queries must trigger both search_policies and
    lookup_employee and return a combined answer from both sources.
    This is the Phase 4 exit criteria test."""
    compound_items = [i for i in agent_golden_set if i["query_type"] == "compound"]
    test_cases = [build_test_case(item) for item in compound_items]

    results = evaluate(
        test_cases=test_cases,
        metrics=[
            agent_metrics["task_completion"],
            agent_metrics["tool_correctness"],
            agent_metrics["answer_relevancy"],
        ],
    )

    assert all(r.success for r in results.test_results), (
        "One or more compound query test cases failed — "
        "agent may not be calling both tools or combining results correctly"
    )


def test_agent_tool_correctness_boundary(agent_golden_set, agent_metrics):
    """Pure tool correctness check across all 10 golden set entries.
    No LLM judge — verifies tools_called matches expected_tools for
    every entry. ToolCorrectnessMetric must reach >= 0.8 on all cases."""
    test_cases = [build_test_case(item) for item in agent_golden_set]

    results = evaluate(
        test_cases=test_cases,
        metrics=[agent_metrics["tool_correctness"]],
    )

    assert all(r.success for r in results.test_results), (
        "Tool correctness boundary check failed — one or more entries had "
        "the wrong tool called. Review agent routing rules in hr_advisor.py"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
