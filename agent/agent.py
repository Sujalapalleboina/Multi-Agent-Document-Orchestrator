import os
import sys
import json
import httpx
from dotenv import load_dotenv
from typing import AsyncGenerator
import re
import asyncio
import agent.planner

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'mcp_server'))

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_active_documents_metadata",
            "description": "Get metadata for all active documents in a container",
            "parameters": {
                "type": "object",
                "properties": {
                    "container_id": {
                        "type": "string",
                        "description": "The container ID e.g. container_001"
                    }
                },
                "required": ["container_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "translate_document_preserving_structure",
            "description": "Translate documents to a target language",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of document IDs to translate"
                    },
                    "destinationLanguageThreeLetterCode": {
                        "type": "string",
                        "description": "3-letter language code e.g. spa, fra, deu"
                    },
                    "container_id": {
                        "type": "string",
                        "description": "The container ID"
                    }
                },
                "required": ["document_id", "destinationLanguageThreeLetterCode", "container_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_document_insights",
            "description": "Get AI insights for documents in a container",
            "parameters": {
                "type": "object",
                "properties": {
                    "container_id": {
                        "type": "string",
                        "description": "The container ID"
                    },
                    "model": {
                        "type": "string",
                        "description": "Filter by insight type: Classification, Summarisation, Redaction, Keyword"
                    }
                },
                "required": ["container_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "aiagent",
            "description": "Ask a question about documents in a container",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The user question"
                    },
                    "container_id": {
                        "type": "string",
                        "description": "The container ID"
                    }
                },
                "required": ["prompt", "container_id"]
            }
        }
    }
]


async def call_mcp_tool(tool_name: str, tool_args: dict) -> str:
    """Call MCP tool functions directly."""
    try:
        from Sample_FastMCP import (
            get_active_documents_metadata,
            translate_document_preserving_structure,
            get_document_insights,
            aiagent
        )

        if tool_name == "get_active_documents_metadata":
            result = await get_active_documents_metadata(**tool_args)
        elif tool_name == "translate_document_preserving_structure":
            result = await translate_document_preserving_structure(**tool_args)
        elif tool_name == "get_document_insights":
            result = await get_document_insights(**tool_args)
        elif tool_name == "aiagent":
            result = await aiagent(**tool_args)
        else:
            return f"Unknown tool: {tool_name}"

        return json.dumps(result)

    except Exception as e:
        return f"Tool error: {str(e)}"


def detect_language_code(text: str) -> str:
    """Detect language name and return 3-letter ISO code."""
    language_map = {
        "german": "deu", "french": "fra", "spanish": "spa",
        "italian": "ita", "portuguese": "por", "japanese": "jpn",
        "chinese": "zho", "english": "eng", "dutch": "nld",
        "arabic": "ara", "hindi": "hin", "korean": "kor"
    }
    text_lower = text.lower()
    for lang, code in language_map.items():
        if lang in text_lower:
            return code
    return "eng"


def detect_category(text: str) -> str:
    """Detect document category from user request."""
    text_lower = text.lower()
    category_map = {
        "financial": ["financial", "finance"],
        "legal": ["legal", "law"],
        "business": ["business"],
        "compliance": ["compliance"],
        "hr": ["hr", "human resources"],
        "meeting": ["meeting", "minutes"],
        "technical": ["technical", "tech"]
    }
    for category, keywords in category_map.items():
        if any(kw in text_lower for kw in keywords):
            return category
    return None


def detect_container(text: str) -> str:
    """Detect container ID from user request."""
    match = re.search(r'container_\d+', text)
    if match:
        return match.group()
    return "container_001"


async def handle_bulk_translation(
    user_message: str,
    container_id: str,
    lang_code: str,
    category: str = None
) -> AsyncGenerator[str, None]:
    """Handle bulk translation with real document IDs from database."""

    from Sample_FastMCP import get_active_documents_metadata, translate_document_preserving_structure

    # Step 1 — Get all real document IDs
    yield f"event: update\ndata: Fetching all documents from {container_id}...\n\n"
    metadata = await get_active_documents_metadata(container_id=container_id)
    all_docs = metadata.get("documents", [])
    total = metadata.get("total_documents", 0)
    yield f"event: update\ndata: Retrieved {total} documents from {container_id}\n\n"

    # Step 2 — Filter by category if specified
    if category:
        filtered_docs = [d for d in all_docs if d.get("category", "").lower() == category.lower()]
        yield f"event: update\ndata: Filtered to {len(filtered_docs)} {category} documents\n\n"
    else:
        filtered_docs = all_docs

    if not filtered_docs:
        yield f"event: done\ndata: No documents found matching your criteria.\n\n"
        return

    # Step 3 — Extract document IDs
    doc_ids = [d["documentId"] for d in filtered_docs]
    yield f"event: update\ndata: Preparing bulk translation of {len(doc_ids)} documents to {lang_code}...\n\n"

    # Step 4 — Execute bulk translation in batches
    batch_size = 100
    total_successful = 0
    total_failed = 0

    for i in range(0, len(doc_ids), batch_size):
        batch = doc_ids[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(doc_ids) + batch_size - 1) // batch_size

        yield f"event: update\ndata: Processing batch {batch_num}/{total_batches} ({len(batch)} documents)...\n\n"

        try:
            result = await translate_document_preserving_structure(
                document_id=batch,
                destinationLanguageThreeLetterCode=lang_code,
                container_id=container_id
            )
            total_successful += result.get("successful", len(batch))
            total_failed += result.get("failed", 0)
            yield f"event: update\ndata: Batch {batch_num} complete — {result.get('successful', len(batch))} successful\n\n"
        except Exception as e:
            total_failed += len(batch)
            yield f"event: update\ndata: Batch {batch_num} failed: {str(e).replace(chr(10), ' ')}\n\n"

    # Step 5 — Return summary
    yield f"event: done\ndata: Bulk translation complete! {total_successful} documents translated to {lang_code}, {total_failed} failed out of {len(doc_ids)} total.\n\n"


async def run_agent_stream(user_message: str, history: list = None) -> AsyncGenerator[str, None]:
    """Run agent and stream updates in real time."""

    # Step 1 — Show plan
    yield "event: update\ndata: Planning started...\n\n"
    yield "event: update\ndata: [Orchestrator] Initializing multi-agent system...\n\n"
    yield "event: update\ndata: [Orchestrator] Agents ready: PlanningAgent, ToolExecutorAgent, BulkWorkerAgent, ResponseFormatterAgent\n\n"
    plan = agent.planner.create_plan(user_message)
    plan_escaped = plan.replace("\n", " | ")
    yield f"event: update\ndata: {plan_escaped}\n\n"

    # Step 2 — Plan Mode: check if clarification needed
    msg_lower_check = user_message.lower()

    # ═══ PLAN MODE / CLARIFICATION MODE ═══
    # Detects ambiguous requests and asks targeted clarifying questions
    # before executing any tool — prevents incorrect assumptions and wrong tool calls
    # Dashboard request needs clarification
    if "dashboard" in msg_lower_check and len(user_message.split()) < 8:
        yield "event: update\ndata: Entering Plan Mode — request needs clarification...\n\n"
        yield "event: clarify\ndata: Q1: Should the dashboard be HTML or a text report?\n\n"
        yield "event: clarify\ndata: Q2: Which document categories should be included? (financial, legal, all)\n\n"
        yield "event: clarify\ndata: Q3: Which container should I use? (e.g. container_001)\n\n"
        yield "event: done\ndata: Please answer the above questions so I can build exactly what you need.\n\n"
        return

    # Convert request needs clarification
    if "convert" in msg_lower_check and len(user_message.split()) < 8:
        yield "event: update\ndata: Entering Plan Mode — request needs clarification...\n\n"
        yield "event: clarify\ndata: Q1: What format do you want to convert TO? (e.g. DOCX, PDF, TXT)\n\n"
        yield "event: clarify\ndata: Q2: Which document category? (financial, legal, all)\n\n"
        yield "event: clarify\ndata: Q3: Which container? (e.g. container_001)\n\n"
        yield "event: done\ndata: Please answer the above questions so I can proceed correctly.\n\n"
        return

    # Vague single word requests
    if len(user_message.split()) <= 2:
        yield "event: update\ndata: Entering Plan Mode — request is too vague...\n\n"
        yield "event: clarify\ndata: Q1: What would you like to do? (translate, summarize, list, insights)\n\n"
        yield "event: clarify\ndata: Q2: Which container should I use? (e.g. container_001)\n\n"
        yield "event: clarify\ndata: Q3: Any specific document category? (financial, legal, business)\n\n"
        yield "event: done\ndata: Please provide more details so I can help you accurately.\n\n"
        return

    # Step 3 — Detect if this is a bulk translation request
    msg_lower = user_message.lower()
    if "translate" in msg_lower:
        container_id = detect_container(user_message)
        lang_code = detect_language_code(user_message)
        category = detect_category(user_message)
        yield f"event: update\ndata: Detected bulk translation request — container: {container_id}, language: {lang_code}, category: {category or 'all'}\n\n"
        async for update in handle_bulk_translation(user_message, container_id, lang_code, category):
            yield update
        return

    # Detect web/news queries — not supported by document tools
    web_keywords = ["news", "latest", "current events", "today", "weather", "stock", "price of"]
    if any(kw in msg_lower for kw in web_keywords):
        yield "event: update\ndata: Detected web query — outside document management scope\n\n"
        yield "event: done\ndata: I am a document management agent and can only answer questions about your documents. For web searches or current news, please use a web browser or search engine.\n\n"
        return

    # Step 4 — For all other requests use LLM tool calling
    yield "event: update\ndata: Selecting the right tool...\n\n"

    system_prompt = (
        "You are a helpful document management assistant. "
        "You have access to tools to manage documents in containers. "
        "Default container is container_001 unless the user specifies otherwise. "
        "Keep responses very brief and concise. "
        "Use tools to answer the user's request."
    )
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    max_iterations = 5
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        # Retry logic with exponential backoff
        max_retries = 3
        retry_delay = 1
        result = None
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    response = await client.post(
                        GROQ_API_URL,
                        headers=headers,
                        json={
                            "model": "llama-3.3-70b-versatile",
                            "messages": messages,
                            "tools": TOOLS,
                            "tool_choice": "auto",
                            "temperature": 0,
                            "max_tokens": 2000
                        }
                    )
                    result = response.json()
                    break
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (2 ** attempt))
                else:
                    yield f"event: error\ndata: Request failed after {max_retries} attempts: {str(e).replace(chr(10), ' ')}\n\n"
                    return

        if result is None:
            return  # already yielded error above
        if "error" in result:
            error_msg = result['error']
            if 'tool_use_failed' in str(error_msg) or 'failed_generation' in str(error_msg):
                yield "event: update\ndata: Tool call failed — please rephrase your request.\n\n"
                yield "event: done\ndata: I understood your request but had trouble executing it.\n\n"
                return
            yield f"event: error\ndata: Error: {str(error_msg).replace(chr(10), ' ')}\n\n"
            return

        choice = result["choices"][0]
        message = choice["message"]
        messages.append(message)

        if choice["finish_reason"] == "tool_calls":
            for tool_call in message.get("tool_calls", []):
                tool_name = tool_call["function"]["name"]
                tool_args = json.loads(tool_call["function"]["arguments"])

                yield f"event: update\ndata: Tool selected: {tool_name}\n\n"
                yield f"event: update\ndata: Executing {tool_name}...\n\n"

                tool_result = await call_mcp_tool(tool_name, tool_args)

                try:
                    parsed = json.loads(tool_result)
                    if "total_documents" in parsed:
                        yield f"event: update\ndata: Retrieved {parsed['total_documents']} documents from {parsed.get('container_id', '')}\n\n"
                    if "successful" in parsed:
                        yield f"event: update\ndata: Operation complete: {parsed['successful']} successful, {parsed['failed']} failed\n\n"
                except:
                    pass

                truncated_result = str(tool_result)[:3000]
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": truncated_result
                })
                yield f"event: update\ndata: Tool execution complete. Generating response...\n\n"

        else:
            final_answer = message.get("content", "No response generated.")
            final_answer_escaped = final_answer.replace("\n", " ").strip()
            yield f"event: done\ndata: {final_answer_escaped}\n\n"
            return

    yield "event: done\ndata: Max iterations reached. Please try a more specific question.\n\n"