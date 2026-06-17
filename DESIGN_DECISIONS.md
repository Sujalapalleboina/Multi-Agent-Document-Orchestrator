# Design Decisions — AI Document Management Agent

## Why This Architecture

### API-Driven Over CLI/TUI
The assessment explicitly required an API-driven system.
A FastAPI server with SSE streaming allows any client (web, mobile, CLI)
to consume the agent without being locked into a terminal interface.
This mirrors production systems like OpenCode and Hermes Agent.

### Why Groq Instead of Anthropic
Groq provides a free tier with OpenAI-compatible API.
The agent architecture is identical regardless of LLM provider.
Switching to Anthropic requires only changing the API key and base URL in agent.py.
In production, Anthropic Claude would be preferred for better tool calling reliability.

### Why Direct MCP Tool Imports Instead of HTTP Calls
FastMCP SSE transport does not support simple HTTP POST tool calls.
Importing tool functions directly avoids network overhead and simplifies error handling.
In production, a proper MCP client SDK would be used for full protocol compliance.

## Bulk Operation Strategy

### Problem
The database has 36,000 documents across 4 containers (9,000 per container).
Passing all document IDs to the LLM would exceed context limits.
Naive tool loops inside the LLM are slow and unpredictable.

### Solution
1. Fetch ALL real document IDs from database first using get_active_documents_metadata
2. Filter by category in Python code (not in LLM) — faster and more reliable
3. Process in batches of 100 documents per API call
4. Track success and failure per batch
5. Return final summary to user

This approach scales to millions of documents without any LLM context issues.

### Batch Size Decision
100 documents per batch was chosen because:
- Large enough to minimize API call overhead
- Small enough to handle partial failures gracefully
- Matches the concurrency semaphore limit in the MCP tool (20 parallel)

## Streaming Architecture

### Why SSE Over WebSockets
SSE is simpler, works over standard HTTP, and is one-directional (server to client).
For agent execution updates, SSE is perfect — the client only needs to receive updates.
WebSockets add unnecessary complexity for this use case.

### Event Types Used
- event: update — intermediate execution steps
- event: clarify — clarifying questions in Plan Mode
- event: error — error messages
- event: done — final answer

## Plan Mode Design

### Why Interrogation Mode Matters
Blindly executing unclear requests wastes compute and produces wrong results.
Plan Mode forces the agent to gather required information before acting.
This mirrors how a professional consultant would handle an ambiguous brief.

### Triggers for Plan Mode
- "dashboard" requests — need format, categories, container
- "convert" requests — need target format, category, container
- Very short requests (2 words or less) — always too vague to execute

## Tradeoffs Considered

### LLM Tool Calling vs Rule-Based Routing
For bulk translation, rule-based detection was chosen over LLM tool calling.
Reason: LLM guesses wrong document IDs when not given real data.
Rule-based detection is deterministic, faster, and more reliable for known patterns.
LLM tool calling is used for general queries where intent is unpredictable.

### Stateless vs Stateful Agent
The agent is stateless — each request is independent.
This simplifies scaling (multiple instances can run in parallel).
Tradeoff: no conversation memory between requests.
In production, a session store (Redis) would be added for multi-turn conversations.

### Truncating Tool Results
Tool results are truncated to 3,000 characters before sending to LLM.
This avoids token limit errors on large database responses.
Tradeoff: LLM sees less context, but for most queries this is sufficient.

## Scaling Considerations

### Current Architecture Handles
- 36,000 documents across 4 containers (9,000 per container)
- Batch processing with 100 docs per batch
- 20 concurrent translations per batch (semaphore controlled)

### Production Scaling Would Add
- Redis for session state and job queues
- Celery workers for background bulk operations
- Progress stored in database, polled by client
- Multiple agent instances behind a load balancer
- Retry logic with exponential backoff

## Failure Recovery

### Current Implementation
- Per-batch try/catch — one batch failure does not stop others
- Failed document IDs tracked and reported in final summary
- LLM errors return user-friendly messages
- 60 second timeout on all HTTP calls

### Production Would Add
- Automatic retry for failed batches (3 attempts)
- Dead letter queue for permanently failed documents
- Alert system for high failure rates
- Detailed error logs per document

Note: Multi-turn clarification requires session state. Current implementation asks clarifying questions but the client must re-send a complete request with the answers included. Production would use Redis for session continuity.

## Known Limitations

### Web Search Queries
The agent is scoped to document management tools only. Web queries (news, current events) 
are detected and returned with an honest message rather than routing to the wrong tool.

### Document Conversion (PDF to DOCX)
No conversion tool exists in the provided MCP server. The agent correctly enters Plan Mode 
and asks clarifying questions, but conversion execution is not implemented. In production, 
a conversion tool would be added to the MCP server.