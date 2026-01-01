from fastmcp import FastMCP

from app.tools.execution import register_execution_tools
from app.tools.market_data import register_market_tools
from app.tools.research import register_research_tools
from app.tools.trading import register_trading_tools

# Initialize FastMCP server
mcp = FastMCP("ReadyTrader-Stocks")

# Register Tools
register_market_tools(mcp)
register_trading_tools(mcp)
register_research_tools(mcp)
register_execution_tools(mcp)

if __name__ == "__main__":
    mcp.run()
