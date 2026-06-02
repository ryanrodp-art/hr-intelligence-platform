from fastmcp import FastMCP
import logging

mcp = FastMCP(
    "ARIA HR MCP Server",
    instructions=(
        "You are connected to the ARIA HR MCP Server for Acme Corp. "
        "This server provides tools to check employee leave balances, "
        "submit leave requests, look up org chart information, and "
        "search HR policy documents. All write operations require "
        "valid employee_id in EMP-XXXX format."
    )
)

from mcp_server.tools import leave_tool
from mcp_server.tools import org_chart_tool
from mcp_server.tools import policy_lookup_tool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting ARIA HR MCP Server on port 8002...")
    logger.info("Tools registered: check_leave_balance, "
                "submit_leave_request, get_org_chart, policy_lookup")
    mcp.run(transport="http", host="0.0.0.0", port=8002)
