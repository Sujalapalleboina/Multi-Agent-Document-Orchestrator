import logging
import time
import uuid
from typing import Optional

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger("agent.observability")


class ExecutionTracer:
    """
    Lightweight observability layer for agent execution.
    Tracks request lifecycle, tool calls, and performance metrics.
    In production this would emit to OpenTelemetry / Prometheus.
    """

    def __init__(self, session_id: Optional[str] = None):
        self.trace_id = str(uuid.uuid4())[:8]
        self.session_id = session_id or "no-session"
        self.start_time = time.time()
        self.events = []
        self.tool_calls = []
        self.errors = []

    def log_request(self, user_message: str, mode: str):
        """Log incoming request."""
        self.events.append({
            "type": "request",
            "message": user_message[:100],
            "mode": mode,
            "timestamp": time.time()
        })
        logger.info(
            f"[TRACE:{self.trace_id}] Request received | "
            f"session:{self.session_id} | mode:{mode} | "
            f"message:{user_message[:50]!r}"
        )

    def log_tool_call(self, tool_name: str, args: dict):
        """Log tool invocation.
        Note: tool-level tracing requires tracer to be passed into agent/orchestrator.
        Currently tracked at request level only. Full tool tracing is a production enhancement.
        """
        self.tool_calls.append({
            "tool": tool_name,
            "args": str(args)[:100],
            "timestamp": time.time()
        })
        logger.info(
            f"[TRACE:{self.trace_id}] Tool call | "
            f"tool:{tool_name} | args:{str(args)[:50]}"
        )

    def log_tool_result(self, tool_name: str, success: bool, duration_ms: float):
        """Log tool execution result."""
        logger.info(
            f"[TRACE:{self.trace_id}] Tool result | "
            f"tool:{tool_name} | success:{success} | duration:{duration_ms:.0f}ms"
        )

    def log_error(self, error: str, context: str = ""):
        """Log error with context."""
        self.errors.append({
            "error": error[:200],
            "context": context,
            "timestamp": time.time()
        })
        logger.error(
            f"[TRACE:{self.trace_id}] Error | "
            f"context:{context} | error:{error[:100]}"
        )

    def log_batch_progress(self, batch_num: int, total_batches: int,
                           successful: int, failed: int):
        """Log bulk operation progress."""
        logger.info(
            f"[TRACE:{self.trace_id}] Batch progress | "
            f"batch:{batch_num}/{total_batches} | "
            f"successful:{successful} | failed:{failed}"
        )

    def log_completion(self, status: str):
        """Log request completion with full metrics."""
        duration = (time.time() - self.start_time) * 1000
        logger.info(
            f"[TRACE:{self.trace_id}] Request complete | "
            f"status:{status} | duration:{duration:.0f}ms | "
            f"tool_calls:{len(self.tool_calls)} | errors:{len(self.errors)}"
        )
        return {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "duration_ms": round(duration, 2),
            "tool_calls": len(self.tool_calls),
            "errors": len(self.errors),
            "status": status
        }

    def get_metrics(self) -> dict:
        """Return current execution metrics."""
        return {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "elapsed_ms": round((time.time() - self.start_time) * 1000, 2),
            "tool_calls": len(self.tool_calls),
            "errors": len(self.errors),
            "events": len(self.events)
        }


# Global metrics store — in production use Prometheus counters
_global_metrics = {
    "total_requests": 0,
    "total_errors": 0,
    "total_tool_calls": 0,
    "total_bulk_operations": 0,
    "total_documents_processed": 0
}


def increment_metric(key: str, value: int = 1):
    """Increment a global metric counter."""
    if key in _global_metrics:
        _global_metrics[key] += value


def get_global_metrics() -> dict:
    """Return all global metrics."""
    return dict(_global_metrics)