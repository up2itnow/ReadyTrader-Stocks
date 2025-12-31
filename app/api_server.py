import asyncio
import json
import os
from typing import Set

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.core.config import settings

# Import core components from the main server
from app.core.container import global_container
from marketdata.store import TickerSnapshot
from observability import build_log_context, log_event

# Initial context
API_CTX = build_log_context(tool="api_server")

app = FastAPI(title="ReadyTrader-Stocks Modern API")

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to your frontend domain
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active WebSocket connections
active_connections: Set[WebSocket] = set()

def broadcast_tick(snap: TickerSnapshot):
    """
    Callback for marketdata_ws_store updates.
    """
    if not active_connections:
        return
        
    payload = {
        "type": "TICKER_UPDATE",
        "data": snap.to_dict()
    }
    
    # We need to run this in the event loop of the FastAPI app
    # Since this callback might be triggered from a background thread
    # We use a global loop reference or call_soon_threadsafe
    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.create_task(broadcast_all(payload))

async def broadcast_all(payload: dict):
    if not active_connections:
        return
    message = json.dumps(payload)
    disconnected = set()
    for websocket in active_connections:
        try:
            await websocket.send_text(message)
        except Exception:
            disconnected.add(websocket)
            
    for ws in disconnected:
        active_connections.remove(ws)

# Subscribe to ticker updates from the WebSocket store
global_container.marketdata_ws_store.subscribe(broadcast_tick)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    log_event("api_client_connected", ctx=API_CTX, data={"active_connections": len(active_connections)})
    try:
        while True:
            # Keep connection open
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        log_event("api_client_disconnected", ctx=API_CTX, data={"active_connections": len(active_connections)})

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "mode": "paper" if settings.PAPER_MODE else "live"}

@app.get("/api/pending-approvals")
async def get_pending_approvals():
    """
    Return list of trades awaiting manual approval.
    """
    return global_container.execution_store.list_pending()

class ApprovalRequest(BaseModel):
    request_id: str
    confirm_token: str
    approve: bool

@app.post("/api/approve-trade")
async def approve_trade(req: ApprovalRequest):
    """
    Approve or cancel a pending trade proposal.
    """
    try:
        if req.approve:
            # 1. Confirm the proposal in the store (validates token and expiration)
            try:
                proposal = global_container.execution_store.confirm(req.request_id, req.confirm_token)
            except ValueError as ve:
                raise HTTPException(status_code=400, detail=str(ve))
            
            # 2. Execute based on kind
            if proposal.kind == "stock_order":
                p = proposal.payload
                
                if settings.PAPER_MODE:
                    res = global_container.paper_engine.execute_trade(
                        user_id="agent_zero",
                        side=p["side"],
                        symbol=p["symbol"],
                        amount=p["amount"],
                        price=p.get("price", 0.0),
                        rationale=p.get("rationale", "api_approved")
                    )
                    return {"ok": True, "result": res}
                else:
                    # Live Brokerage Execution
                    exchange = p.get("exchange", "alpaca").lower()
                    if exchange not in global_container.brokerages:
                        raise HTTPException(status_code=400, detail=f"Brokerage {exchange} is not supported.")
                    
                    brokerage = global_container.brokerages[exchange]
                    if not brokerage.is_available():
                        raise HTTPException(status_code=400, detail=f"Brokerage {exchange} is not configured with API keys.")
                    
                    try:
                        res = brokerage.place_order(
                            symbol=p["symbol"],
                            side=p["side"],
                            qty=p["amount"],
                            order_type=p.get("order_type", "market"),
                            price=p.get("price") if p.get("price", 0) > 0 else None
                        )
                        return {"ok": True, "result": res}
                    except Exception as e:
                        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")
            
            return {"ok": False, "error": "Unknown proposal kind"}
        else:
            success = global_container.execution_store.cancel(req.request_id)
            return {"ok": success}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/portfolio")
async def get_portfolio():
    """
    Get current portfolio state (paper or live).
    """
    if settings.PAPER_MODE:
        balances = global_container.paper_engine.get_balances("agent_zero")
        pnl = global_container.paper_engine.get_risk_metrics("agent_zero")
        return {"balances": balances, "metrics": pnl}
    else:
        # For live mode, we'd need to query the wallet/CEX
        return {"error": "Live portfolio view not yet implemented in API"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", 8000))
    host = os.getenv("API_HOST", "127.0.0.1")
    log_event("api_server_started", ctx=API_CTX, data={"port": port, "host": host})
    uvicorn.run(app, host=host, port=port)
