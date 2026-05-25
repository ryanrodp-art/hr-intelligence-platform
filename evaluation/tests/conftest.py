"""DeepEval pytest configuration for ARIA HR Intelligence Platform.
This conftest.py is automatically loaded by pytest before any test runs.
It configures the judge LLM used to evaluate all DeepEval metrics."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
))))

import pytest

# DeepEval uses a judge LLM to evaluate your LLM's outputs.
# We use GPT-4o as the judge (same model, evaluating itself is acceptable).
# The OPENAI_API_KEY is read from the environment automatically.
# In Phase 7 we will add Confident AI integration here.


@pytest.fixture(scope="session")
def deepeval_config():
    """Configure the DeepEval judge LLM for the test session."""
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    print("DeepEval judge LLM: GPT-4o")
    return {"judge_model": "gpt-4o"}
