import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("ARIA HR MCP Server")
    logger.info("Transport: HTTP | Port: 8002")
    logger.info("Endpoint: http://localhost:8002/mcp")
    logger.info("Tools: check_leave_balance, submit_leave_request,")
    logger.info("       get_org_chart, policy_lookup")
    logger.info("=" * 50)
    from mcp_server.server import mcp
    mcp.run(transport="http", host="0.0.0.0", port=8002)
