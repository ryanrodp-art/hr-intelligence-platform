from mcp_server.server import mcp
from vector_store.searcher import search_and_format
import logging

logger = logging.getLogger(__name__)


@mcp.tool
def policy_lookup(query: str) -> str:
    """
    Search Acme Corp HR policy documents for a specific clause,
    rule, or entitlement. Use this tool when an employee asks
    about a specific policy topic and needs the exact wording
    or details from the official policy documents.
    Returns the most relevant policy excerpts with source citations.
    query should be a specific topic or keyword, for example:
    'parental leave entitlement', 'probation period notice',
    '401k contribution matching'.
    """
    logger.info("Policy lookup MCP tool called: %s", query[:50])
    result = search_and_format(query, n_results=3)

    if not result or result == "No relevant information found.":
        return (
            "No policy information found for that query. "
            "Please contact HR at hr@acmecorp.com for assistance."
        )

    return result
