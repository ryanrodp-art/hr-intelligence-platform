import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))

import pytest
import json
import time
import asyncio
from deepeval import evaluate
from deepeval.metrics import AnswerRelevancyMetric, TaskCompletionMetric
from deepeval.test_case import LLMTestCase
from agents.single.hr_advisor import run_hr_advisor_with_mcp

MCP_SERVER_URL = "http://localhost:8002/mcp"


def get_mcp_response(question: str):
    result = asyncio.run(run_hr_advisor_with_mcp(question))
    time.sleep(3.0)
    return result


def build_mcp_test_case(item: dict) -> LLMTestCase:
    result = get_mcp_response(item["input"])
    return LLMTestCase(
        input=item["input"],
        actual_output=result.answer,
        expected_output=item["expected_output"],
    )


@pytest.fixture
def mcp_golden_set():
    dataset_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "datasets",
        "mcp_golden_set.json",
    )
    with open(dataset_path) as f:
        return json.load(f)


@pytest.fixture
def mcp_metrics():
    return {
        "task_completion": TaskCompletionMetric(threshold=0.7, model="gpt-4o"),
        "answer_relevancy": AnswerRelevancyMetric(threshold=0.7, model="gpt-4o"),
    }


def test_mcp_read_tools(mcp_golden_set, mcp_metrics):
    """MCP read tools must return accurate employee and org data."""
    items = [i for i in mcp_golden_set if i["query_type"] == "read"][:3]
    test_cases = [build_mcp_test_case(item) for item in items]
    results = evaluate(
        test_cases=test_cases,
        metrics=[mcp_metrics["task_completion"], mcp_metrics["answer_relevancy"]],
    )
    assert all(r.success for r in results.test_results)


def test_mcp_write_tool(mcp_golden_set, mcp_metrics):
    """submit_leave_request must confirm write and return pending status."""
    items = [i for i in mcp_golden_set if i["query_type"] == "write"][:3]
    test_cases = [build_mcp_test_case(item) for item in items]
    results = evaluate(
        test_cases=test_cases,
        metrics=[mcp_metrics["task_completion"], mcp_metrics["answer_relevancy"]],
    )
    assert all(r.success for r in results.test_results)


def test_mcp_cancel_tool(mcp_golden_set, mcp_metrics):
    """cancel_leave_request must confirm deletion and return removed status.

    NOTE: This test depends on test_mcp_write_tool having run first in the
    same session to create the pending records that are cancelled here.
    Run order: test_mcp_write_tool → test_mcp_cancel_tool.
    """
    items = [i for i in mcp_golden_set if i["query_type"] == "cancel"][:3]
    test_cases = [build_mcp_test_case(item) for item in items]
    results = evaluate(
        test_cases=test_cases,
        metrics=[mcp_metrics["task_completion"], mcp_metrics["answer_relevancy"]],
    )
    assert all(r.success for r in results.test_results)


def test_mcp_multi_step(mcp_golden_set, mcp_metrics):
    """Multi-step MCP sequences must handle both tools correctly."""
    items = [i for i in mcp_golden_set if i["query_type"] == "multi_step"]
    test_cases = [build_mcp_test_case(item) for item in items]
    results = evaluate(
        test_cases=test_cases,
        metrics=[mcp_metrics["task_completion"], mcp_metrics["answer_relevancy"]],
    )
    assert all(r.success for r in results.test_results)


def test_mcp_tool_routing_boundary(mcp_golden_set):
    """Every golden set entry must invoke its expected MCP tool.

    Covers all 5 MCP tools across 13 entries:
      read (4)         — check_leave_balance x2, get_org_chart x2
      write (3)        — submit_leave_request x3
      cancel (3)       — cancel_leave_request x3
      multi_step (3)   — check_leave_balance, get_org_chart, submit_leave_request

    Cancel entries will call cancel_leave_request regardless of whether a
    pending record exists — the tool is always invoked, the response varies.
    """
    failures = []
    for item in mcp_golden_set:
        result = get_mcp_response(item["input"])
        if item["expected_mcp_tool"] not in result.tools_used:
            failures.append(
                f"Expected {item['expected_mcp_tool']} for: {item['input'][:50]}"
                f" — got {result.tools_used}"
            )
    assert not failures, "\n".join(failures)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
