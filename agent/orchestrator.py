import asyncio
import json
import re
import sys
import os
from typing import AsyncGenerator

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'mcp_server'))


# ═══════════════════════════════════════════════════════
# WORKER AGENT BASE CLASS
# ═══════════════════════════════════════════════════════

class WorkerAgent:
    """Base class for all worker agents."""

    def __init__(self, name: str):
        self.name = name
        self.status = "idle"

    async def run(self, task: dict) -> dict:
        raise NotImplementedError


# ═══════════════════════════════════════════════════════
# PLANNING AGENT
# ═══════════════════════════════════════════════════════

class PlanningAgent(WorkerAgent):
    """Decomposes user request into executable tasks."""

    def __init__(self):
        super().__init__("PlanningAgent")

    async def run(self, task: dict) -> dict:
        self.status = "running"
        user_message = task.get("user_message", "")
        msg_lower = user_message.lower()

        # Detect intent
        if "translate" in msg_lower:
            intent = "bulk_translation"
        elif "insight" in msg_lower or "summarize" in msg_lower or "summary" in msg_lower:
            intent = "get_insights"
        elif "how many" in msg_lower or "count" in msg_lower or "list" in msg_lower:
            intent = "get_metadata"
        elif "dashboard" in msg_lower:
            intent = "create_dashboard"
        elif "convert" in msg_lower:
            intent = "convert_documents"
        else:
            intent = "general_query"

        # Detect container
        match = re.search(r'container_\d+', user_message)
        container_id = match.group() if match else "container_001"

        # Detect language
        language_map = {
            "german": "deu", "french": "fra", "spanish": "spa",
            "italian": "ita", "portuguese": "por", "japanese": "jpn",
            "chinese": "zho", "english": "eng", "dutch": "nld"
        }
        lang_code = "eng"
        for lang, code in language_map.items():
            if lang in msg_lower:
                lang_code = code
                break

        # Detect category
        category = None
        category_map = {
            "financial": ["financial", "finance"],
            "legal": ["legal", "law"],
            "business": ["business"],
            "compliance": ["compliance"],
            "hr": ["hr", "human resources"],
            "meeting": ["meeting", "minutes"],
            "technical": ["technical", "tech"]
        }
        for cat, keywords in category_map.items():
            if any(kw in msg_lower for kw in keywords):
                category = cat
                break

        self.status = "done"
        return {
            "agent": self.name,
            "intent": intent,
            "container_id": container_id,
            "lang_code": lang_code,
            "category": category,
            "user_message": user_message
        }


# ═══════════════════════════════════════════════════════
# TOOL EXECUTOR AGENT
# ═══════════════════════════════════════════════════════

class ToolExecutorAgent(WorkerAgent):
    """Executes MCP tools based on planning agent output."""

    def __init__(self):
        super().__init__("ToolExecutorAgent")

    async def run(self, task: dict) -> dict:
        self.status = "running"
        tool_name = task.get("tool_name")
        tool_args = task.get("tool_args", {})

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
                result = {"error": f"Unknown tool: {tool_name}"}

            self.status = "done"
            return {"agent": self.name, "tool": tool_name, "result": result}

        except Exception as e:
            self.status = "error"
            return {"agent": self.name, "tool": tool_name, "error": str(e)}


# ═══════════════════════════════════════════════════════
# BULK WORKER AGENT
# ═══════════════════════════════════════════════════════

class BulkWorkerAgent(WorkerAgent):
    """Handles large scale bulk operations with batching."""

    def __init__(self):
        super().__init__("BulkWorkerAgent")

    async def run(self, task: dict) -> dict:
        self.status = "running"
        doc_ids = task.get("doc_ids", [])
        lang_code = task.get("lang_code", "eng")
        container_id = task.get("container_id", "container_001")
        batch_size = task.get("batch_size", 100)

        from Sample_FastMCP import translate_document_preserving_structure

        total_successful = 0
        total_failed = 0
        batch_results = []

        for i in range(0, len(doc_ids), batch_size):
            batch = doc_ids[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(doc_ids) + batch_size - 1) // batch_size

            try:
                result = await translate_document_preserving_structure(
                    document_id=batch,
                    destinationLanguageThreeLetterCode=lang_code,
                    container_id=container_id
                )
                successful = result.get("successful", len(batch))
                failed = result.get("failed", 0)
                total_successful += successful
                total_failed += failed
                batch_results.append({
                    "batch": batch_num,
                    "total_batches": total_batches,
                    "successful": successful,
                    "failed": failed
                })
            except Exception as e:
                total_failed += len(batch)
                batch_results.append({
                    "batch": batch_num,
                    "total_batches": total_batches,
                    "error": str(e)
                })

        self.status = "done"
        return {
            "agent": self.name,
            "total_successful": total_successful,
            "total_failed": total_failed,
            "total_docs": len(doc_ids),
            "lang_code": lang_code,
            "batch_results": batch_results
        }


# ═══════════════════════════════════════════════════════
# RESPONSE FORMATTER AGENT
# ═══════════════════════════════════════════════════════

class ResponseFormatterAgent(WorkerAgent):
    """Formats final response for the user."""

    def __init__(self):
        super().__init__("ResponseFormatterAgent")

    async def run(self, task: dict) -> dict:
        self.status = "running"
        intent = task.get("intent")
        data = task.get("data", {})

        if intent == "bulk_translation":
            message = (
                f"Bulk translation complete!\n"
                f"Successfully translated: {data.get('total_successful', 0)} documents\n"
                f"Failed: {data.get('total_failed', 0)} documents\n"
                f"Total processed: {data.get('total_docs', 0)} documents\n"
                f"Target language: {data.get('lang_code', '')}"
            )
        elif intent == "get_metadata":
            total = data.get("total_documents", 0)
            container = data.get("container_id", "")
            message = f"Found {total} documents in {container}."
        else:
            message = str(data)

        self.status = "done"
        return {"agent": self.name, "message": message}


# ═══════════════════════════════════════════════════════
# MASTER ORCHESTRATOR
# ═══════════════════════════════════════════════════════

class MasterOrchestrator:
    """
    OpenCode-style Master Orchestrator.
    Spawns and coordinates worker agents to handle user requests.
    """

    def __init__(self):
        self.planning_agent = PlanningAgent()
        self.tool_executor = ToolExecutorAgent()
        self.bulk_worker = BulkWorkerAgent()
        self.formatter = ResponseFormatterAgent()

    async def run(self, user_message: str) -> AsyncGenerator[str, None]:
        safe_msg = user_message.replace("\n", " ").strip()
        yield f"event: update\ndata: [Orchestrator] Received request: {safe_msg}\n\n"

        # Plan Mode — check for ambiguous requests before doing anything
        msg_lower = user_message.lower()

        if "dashboard" in msg_lower and len(user_message.split()) < 8 and "container_" not in msg_lower and "html" not in msg_lower:
            yield "event: update\ndata: [Orchestrator] Entering Plan Mode — request needs clarification...\n\n"
            yield "event: clarify\ndata: Q1: Should the dashboard be HTML or a text report?\n\n"
            yield "event: clarify\ndata: Q2: Which document categories? (financial, legal, all)\n\n"
            yield "event: clarify\ndata: Q3: Which container? (e.g. container_001)\n\n"
            yield "event: done\ndata: [Orchestrator] Please answer the above questions so I can proceed.\n\n"
            return

        if "convert" in msg_lower and len(user_message.split()) < 8:
            yield "event: update\ndata: [Orchestrator] Entering Plan Mode — request needs clarification...\n\n"
            yield "event: clarify\ndata: Q1: What format do you want to convert TO? (DOCX, PDF, TXT)\n\n"
            yield "event: clarify\ndata: Q2: Which document category? (financial, legal, all)\n\n"
            yield "event: clarify\ndata: Q3: Which container? (e.g. container_001)\n\n"
            yield "event: done\ndata: [Orchestrator] Please answer the above questions so I can proceed.\n\n"
            return

        if len(user_message.split()) <= 2:
            yield "event: update\ndata: [Orchestrator] Entering Plan Mode — request is too vague...\n\n"
            yield "event: clarify\ndata: Q1: What would you like to do? (translate, summarize, list, insights)\n\n"
            yield "event: clarify\ndata: Q2: Which container? (e.g. container_001)\n\n"
            yield "event: clarify\ndata: Q3: Any specific document category? (financial, legal, business)\n\n"
            yield "event: done\ndata: [Orchestrator] Please provide more details so I can help accurately.\n\n"
            return

        yield f"event: update\ndata: [Orchestrator] Spawning PlanningAgent...\n\n"

        # Step 1 — Planning Agent decomposes the request
        plan = await self.planning_agent.run({"user_message": user_message})
        intent = plan["intent"]
        container_id = plan["container_id"]
        lang_code = plan["lang_code"]
        category = plan["category"]

        yield f"event: update\ndata: [PlanningAgent] Intent detected: {intent}\n\n"
        yield f"event: update\ndata: [PlanningAgent] Container: {container_id} | Language: {lang_code} | Category: {category or 'all'}\n\n"

        # Step 2 — Route to correct worker based on intent
        if intent == "bulk_translation":
            yield f"event: update\ndata: [Orchestrator] Spawning ToolExecutorAgent to fetch documents...\n\n"

            # Tool Executor fetches all documents
            metadata_result = await self.tool_executor.run({
                "tool_name": "get_active_documents_metadata",
                "tool_args": {"container_id": container_id}
            })

            if "error" in metadata_result:
                yield f"event: error\ndata: Failed to fetch documents: {metadata_result['error']}\n\n"
                return
            all_docs = metadata_result["result"].get("documents", [])
            total = metadata_result["result"].get("total_documents", 0)
            yield f"event: update\ndata: [ToolExecutorAgent] Retrieved {total} documents from {container_id}\n\n"

            # Filter by category
            if category:
                filtered = [d for d in all_docs if d.get("category", "").lower() == category.lower()]
                yield f"event: update\ndata: [ToolExecutorAgent] Filtered to {len(filtered)} {category} documents\n\n"
            else:
                filtered = all_docs

            doc_ids = [d["documentId"] for d in filtered]

            # Spawn BulkWorkerAgent — delegates batching, concurrency and error tracking
            yield f"event: update\ndata: [Orchestrator] Spawning BulkWorkerAgent for {len(doc_ids)} documents...\n\n"

            bulk_result = await self.bulk_worker.run({
                "doc_ids": doc_ids,
                "lang_code": lang_code,
                "container_id": container_id,
                "batch_size": 100
            })

            for br in bulk_result["batch_results"]:
                if "error" in br:
                    safe_err = str(br['error']).replace("\n", " ")
                    yield f"event: update\ndata: [BulkWorkerAgent] Batch {br['batch']}/{br['total_batches']} error: {safe_err}\n\n"
                else:
                    yield f"event: update\ndata: [BulkWorkerAgent] Batch {br['batch']}/{br['total_batches']} complete — {br['successful']} successful, {br['failed']} failed\n\n"

            yield f"event: update\ndata: [Orchestrator] Spawning ResponseFormatterAgent...\n\n"
            format_result = await self.formatter.run({
                "intent": intent,
                "data": {
                    "total_successful": bulk_result["total_successful"],
                    "total_failed": bulk_result["total_failed"],
                    "total_docs": bulk_result["total_docs"],
                    "lang_code": lang_code
                }
            })
            summary = format_result["message"].replace("\n", " | ")
            yield f"event: done\ndata: [ResponseFormatterAgent] {summary}\n\n"

        elif intent == "get_metadata":
            yield f"event: update\ndata: [Orchestrator] Spawning ToolExecutorAgent...\n\n"
            result = await self.tool_executor.run({
                "tool_name": "get_active_documents_metadata",
                "tool_args": {"container_id": container_id}
            })
            if "error" in result:
                yield f"event: error\ndata: Failed to fetch metadata: {result['error']}\n\n"
                return
            total = result["result"].get("total_documents", 0)
            yield f"event: update\ndata: [ToolExecutorAgent] Retrieved metadata successfully\n\n"
            yield f"event: update\ndata: [Orchestrator] Spawning ResponseFormatterAgent...\n\n"
            format_result = await self.formatter.run({
                "intent": intent,
                "data": result["result"]
            })
            yield f"event: done\ndata: [ResponseFormatterAgent] {format_result['message']}\n\n"

        elif intent == "get_insights":
            yield f"event: update\ndata: [Orchestrator] Spawning ToolExecutorAgent for insights...\n\n"
            result = await self.tool_executor.run({
                "tool_name": "get_document_insights",
                "tool_args": {"container_id": container_id}
            })
            yield f"event: update\ndata: [ToolExecutorAgent] Insights retrieved successfully\n\n"
            yield f"event: done\ndata: [ResponseFormatterAgent] Document insights retrieved for {container_id}.\n\n"

        elif intent == "create_dashboard":
            yield f"event: update\ndata: [Orchestrator] Spawning DashboardAgent...\n\n"
            from agent.dashboard_generator import generate_html_dashboard
            async for update in generate_html_dashboard(container_id):
                yield update

        else:
            # General query — use aiagent tool
            yield f"event: update\ndata: [Orchestrator] Spawning ToolExecutorAgent for general query...\n\n"
            result = await self.tool_executor.run({
                "tool_name": "aiagent",
                "tool_args": {
                    "prompt": user_message,
                    "container_id": container_id
                }
            })
            answer = result.get("result", "No answer found.")
            answer_escaped = str(answer).replace("\n", " ").strip()
            yield f"event: update\ndata: [ToolExecutorAgent] Query executed successfully\n\n"
            yield f"event: done\ndata: [ResponseFormatterAgent] {answer_escaped[:300]}\n\n"