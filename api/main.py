import sys
import os
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from agent.agent import run_agent_stream
from agent.orchestrator import MasterOrchestrator
from agent.observability import ExecutionTracer, increment_metric, get_global_metrics

app = FastAPI(title="AI Document Agent — OpenCode Style", version="2.0.0")

# In-memory session store for conversation state
# In production this would be Redis
session_store: dict = {}

class ChatRequest(BaseModel):
    message: str
    mode: str = "agent"
    session_id: Optional[str] = None

@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Send a message to the agent.
    mode=agent: standard agent with streaming
    mode=orchestrator: OpenCode-style multi-agent orchestration
    session_id: optional session ID for conversation continuity
    Returns a streaming SSE response with real-time updates.
    """
    # Start observability trace
    tracer = ExecutionTracer(session_id=request.session_id)
    tracer.log_request(request.message, request.mode)
    increment_metric("total_requests")

    # Session state management with unbounded growth protection
    history = None
    if request.session_id:
        # Evict oldest session if store exceeds 1000 entries
        if len(session_store) > 1000:
            oldest = next(iter(session_store))
            del session_store[oldest]
        if request.session_id not in session_store:
            session_store[request.session_id] = {
                "history": [],
                "mode": request.mode
            }
        session = session_store[request.session_id]
        history = session["history"][:]
        session["history"].append({"role": "user", "content": request.message})

    async def traced_stream(stream_gen):
        """Wrap stream with observability."""
        try:
            async for chunk in stream_gen:
                yield chunk
            tracer.log_completion("success")
        except Exception as e:
            tracer.log_error(str(e), context="stream")
            tracer.log_completion("error")
            increment_metric("total_errors")
            yield f"event: error\ndata: Stream error: {str(e).replace(chr(10), ' ')}\n\n"

    if request.mode == "orchestrator":
        orchestrator = MasterOrchestrator()
        # Note: orchestrator mode does not yet consume session history.
        # History is supported in agent mode only.
        return StreamingResponse(
            traced_stream(orchestrator.run(request.message)),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-Trace-ID": tracer.trace_id
            }
        )
    else:
        return StreamingResponse(
            traced_stream(run_agent_stream(request.message, history=history)),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-Trace-ID": tracer.trace_id
            }
        )

@app.get("/health")
async def health():
    """Check if the server is running."""
    return {
        "status": "ok",
        "version": "2.0.0",
        "active_sessions": len(session_store),
        "metrics": get_global_metrics()
    }

@app.get("/metrics")
async def metrics():
    """Return global execution metrics."""
    return get_global_metrics()

@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Clear a session from the store."""
    if session_id in session_store:
        del session_store[session_id]
        return {"status": "cleared", "session_id": session_id}
    return {"status": "not_found", "session_id": session_id}

@app.get("/")
async def root():
    """Root endpoint with usage info."""
    return {
        "name": "AI Document Agent — OpenCode Style",
        "version": "2.0.0",
        "modes": {
            "agent": "Standard agent with streaming",
            "orchestrator": "OpenCode-style multi-agent orchestration"
        },
        "endpoints": {
            "POST /chat": "Send a message",
            "GET /health": "Check server status with metrics",
            "GET /metrics": "Global execution metrics",
            "DELETE /session/{id}": "Clear a session"
        },
        "example": {
            "message": "translate all financial documents to German",
            "mode": "orchestrator",
            "session_id": "user-123"
        }
    }