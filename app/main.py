from fastmcp import FastMCP

from app.tools.intelligence import register_intelligence_tools
from app.tools.market import register_market_tools
from app.tools.research import register_research_tools
from app.tools.trading import register_trading_tools

# Initialize FastMCP server
mcp = FastMCP("ReadyTrader-Stocks")

# Register Tools
register_market_tools(mcp)
register_trading_tools(mcp)
register_intelligence_tools(mcp)
register_research_tools(mcp)

if __name__ == "__main__":
    mcp.run()
