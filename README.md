# AI Document Management Agent

## What This Project Does
An API-driven multi-agent framework for enterprise document management.
Accepts natural language requests, plans execution steps, orchestrates MCP tools,
and streams real-time progress updates via Server-Sent Events (SSE).

## Quick Start

### Step 1 - Install dependencies
```
pip install fastapi uvicorn fastmcp python-dotenv httpx pydantic
```

### Step 2 - Add your API key
Create a `.env` file in the root folder:
```
GROQ_API_KEY=your_groq_api_key_here
```
Get a free key at: https://console.groq.com

### Step 3 - Start the MCP Server
```
fastmcp run mcp_server/Sample_FastMCP.py --transport sse --port 8000
```

### Step 4 - Start the API Server (in a new terminal)
```
uvicorn api.main:app --reload --port 8080
```

### Step 5 - Send a request
```
curl -X POST http://127.0.0.1:8080/chat -H "Content-Type: application/json" -d '{"message": "translate all financial documents to German"}'
```

## API Endpoints
- POST /chat — Send a message to the agent (returns SSE stream)
- GET /health — Check server status
- GET / — Usage information

## Example Queries
- "how many documents are in container_001"
- "translate all financial documents to German"
- "translate all legal documents to French"
- "create dashboard" — triggers Plan Mode
- "convert documents" — triggers Plan Mode
- "what are the payment terms in my documents"

## Project Structure
agent_submission/
├── agent/
│   ├── agent.py               # Main agent with streaming and bulk operations
│   ├── orchestrator.py        # Multi-agent orchestration system
│   ├── planner.py             # Intent-based DAG planner
│   └── dashboard_generator.py # HTML dashboard generator
├── api/
│   └── main.py                # FastAPI server with SSE streaming
├── mcp_server/
│   ├── Sample_FastMCP.py      # 4 MCP tools
│   └── fake_database.db       # 36,000 documents across 4 containers
├── .env.example
├── README.md
├── ARCHITECTURE.md
├── DESIGN_DECISIONS.md
└── requirements.txt

## Technologies Used
- Python 3.x
- FastAPI — API framework
- FastMCP — MCP server and tools
- Groq API (llama-3.3-70b-versatile) — LLM for tool selection
- SQLite — document database
- httpx — async HTTP client
- Server-Sent Events (SSE) — real-time streaming