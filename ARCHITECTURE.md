# Architecture Document — AI Document Management Agent

## System Overview
This system is an API-driven multi-agent framework for enterprise document management.
It accepts natural language requests, plans execution steps, orchestrates MCP tools,
and streams real-time progress updates to the user.

## Architecture Diagram

=== AGENT MODE (mode=agent) ===

User Request (HTTP POST /chat)
│
▼
┌─────────────────────┐
│   FastAPI Server    │  ← Streaming SSE responses
│   (port 8080)       │
└─────────┬───────────┘
│
▼
┌─────────────────────┐
│   Planner Module    │  ← DAG-based task decomposition
│   planner.py        │  ← Detects intent and category
└─────────┬───────────┘
│
▼
┌─────────────────────┐
│   Agent Engine      │  ← LLM tool calling loop
│   agent.py          │  ← Handles bulk + single operations
└─────────┬───────────┘
│
▼
┌─────────────────────┐
│   MCP Tool Layer    │  ← 4 tools connected to database
│   Sample_FastMCP.py │
└─────────┬───────────┘
│
▼
┌──────────────────────────────────┐
│   SQLite Database                │
│   36,000 docs, 4 containers      │
└──────────────────────────────────┘


=== ORCHESTRATOR MODE (mode=orchestrator) ===

User Request (HTTP POST /chat)
│
▼
┌──────────────────────────────────────┐
│        MasterOrchestrator            │  ← Spawns and coordinates agents
└───┬──────────┬───────────┬───────────┘
    │          │           │
    ▼          ▼           ▼
┌────────┐ ┌────────┐ ┌─────────────┐
│Planning│ │  Tool  │ │    Bulk     │
│ Agent  │ │Executor│ │   Worker    │
│        │ │ Agent  │ │   Agent     │
└────────┘ └────────┘ └─────────────┘
    │          │           │
    ▼          ▼           ▼
┌──────────────────────────────────────┐
│     ResponseFormatterAgent           │  ← Formats final SSE output
└──────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────┐
│   MCP Tool Layer (4 tools)           │
│   SQLite DB — 36,000 documents       │
└──────────────────────────────────────┘

## Components

### 1. FastAPI Server (api/main.py)
- Exposes POST /chat endpoint with two modes: agent and orchestrator
- Returns Server-Sent Events (SSE) stream
- Streams real-time execution updates to client
- Exposes GET /health endpoint for monitoring

### 2. Planner (agent/planner.py)
- Detects intent from user request (translate, summarize, list, dashboard)
- Generates a structured execution DAG before any tool runs
- Shows plan to user as first streaming update
- Supports task decomposition into numbered steps

### 3. Agent Engine (agent/agent.py)
- Receives user message and streams updates
- Implements Plan Mode for ambiguous requests
- Detects bulk translation requests and handles them natively
- Uses Groq LLM for general tool selection
- Implements retry and error handling

### 4. MasterOrchestrator (agent/orchestrator.py)
- Spawns and coordinates 4 specialized worker agents
- PlanningAgent — decomposes request into intent, container, language, category
- ToolExecutorAgent — executes MCP tools safely with error handling
- BulkWorkerAgent — handles large scale batching with failure tracking
- ResponseFormatterAgent — formats final response for SSE delivery

### 5. DashboardAgent (agent/dashboard_generator.py)
- Generates real HTML dashboard from document data
- Analyzes categories, languages, and statuses
- Saves downloadable HTML file

### 6. MCP Tool Layer (mcp_server/Sample_FastMCP.py)
Four tools available:
- get_active_documents_metadata — retrieves all documents in a container
- translate_document_preserving_structure — translates single or bulk documents
- get_document_insights — retrieves AI insights (classification, summary, PII, keywords)
- aiagent — RAG-based document Q&A

## Key Design Decisions

### Bulk Operation Strategy
The system never passes document IDs guessed by the LLM.
Instead it:
1. Fetches ALL real document IDs from database first
2. Filters by category in Python (not in LLM)
3. Processes in batches of 100 documents
4. Reports progress per batch
5. Returns final success/failure summary

This avoids context explosion and handles millions of documents reliably.

### Streaming Architecture
Every step of execution is streamed via SSE:
- Planning started
- Tool selected
- Documents retrieved
- Batch progress
- Final answer

This gives users full visibility into agent execution.

### Plan Mode (Interrogation Mode)
For ambiguous requests the agent enters Plan Mode:
- Detects vague requests (dashboard, convert, short messages)
- Asks 3 targeted clarifying questions
- Streams clarifying questions to client; client must re-submit with answers (stateless server)
- Prevents incorrect assumptions

### Scalability Considerations
- Batch size of 100 documents per API call
- Semaphore-based concurrency (20 parallel translations)
- Truncated tool responses to avoid LLM token limits
- Stateless API design — each request is independent

## Failure Handling
- Per-batch error catching — one batch failure does not stop others
- KeyError guards on all tool executor result access
- Failed document IDs are tracked and reported
- LLM tool call failures return user-friendly messages
- Timeout handling on all HTTP calls (60 seconds)

## Example Queries Supported
- "how many documents are in container_001"
- "translate all financial documents to German"
- "translate all legal documents to French"
- "create HTML dashboard for container_001" generates real HTML file
- "create dashboard" triggers Plan Mode
- "convert documents" triggers Plan Mode
- "what are the payment terms in my documents"

## Technologies Used
- Python 3.x
- FastAPI — API framework
- FastMCP — MCP server and tools
- Groq API (llama-3.3-70b-versatile) — LLM for tool selection
- SQLite — document database
- httpx — async HTTP client
- Server-Sent Events (SSE) — real-time streaming