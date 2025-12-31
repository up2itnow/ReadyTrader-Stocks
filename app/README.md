# Application Structure

- **main.py**: The entry point for the FastMCP application. This is the definition of the Agent Tools.
- **api_server.py**: A FastAPI server that provides REST endpoints and WebSocket streams for the frontend or external integrations. It runs alongside the MCP server.
- **core/**: Core engines (Backtest, Paper Trading, Compliance, etc.).
- **tools/**: MCP tool definitions.

