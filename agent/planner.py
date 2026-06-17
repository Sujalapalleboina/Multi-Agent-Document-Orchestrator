from typing import Optional


def create_dag(user_request: str) -> dict:
    """Create a real execution DAG with dependencies."""
    request_lower = user_request.lower()

    if "translate" in request_lower:
        dag = {
            "task_id": "bulk_translation",
            "description": user_request,
            "nodes": [
                {"id": "fetch_metadata", "tool": "get_active_documents_metadata", "depends_on": []},
                {"id": "filter_docs", "tool": "python_filter", "depends_on": ["fetch_metadata"]},
                {"id": "validate_count", "tool": "python_validate", "depends_on": ["filter_docs"]},
                {"id": "bulk_translate", "tool": "translate_document_preserving_structure", "depends_on": ["validate_count"], "parallelizable": True},
                {"id": "report_summary", "tool": "response_formatter", "depends_on": ["bulk_translate"]}
            ],
            "parallelizable": True,
            "estimated_steps": 5
        }
    elif "dashboard" in request_lower:
        dag = {
            "task_id": "dashboard_generation",
            "description": user_request,
            "nodes": [
                {"id": "fetch_metadata", "tool": "get_active_documents_metadata", "depends_on": []},
                {"id": "fetch_insights", "tool": "get_document_insights", "depends_on": []},
                {"id": "analyze_data", "tool": "python_analyze", "depends_on": ["fetch_metadata", "fetch_insights"]},
                {"id": "generate_html", "tool": "dashboard_generator", "depends_on": ["analyze_data"]},
                {"id": "save_file", "tool": "file_writer", "depends_on": ["generate_html"]}
            ],
            "parallelizable": False,
            "estimated_steps": 5
        }
    elif "insight" in request_lower or "summarize" in request_lower:
        dag = {
            "task_id": "get_insights",
            "description": user_request,
            "nodes": [
                {"id": "fetch_insights", "tool": "get_document_insights", "depends_on": []},
                {"id": "format_response", "tool": "response_formatter", "depends_on": ["fetch_insights"]}
            ],
            "parallelizable": False,
            "estimated_steps": 2
        }
    elif "how many" in request_lower or "count" in request_lower or "list" in request_lower:
        dag = {
            "task_id": "get_metadata",
            "description": user_request,
            "nodes": [
                {"id": "fetch_metadata", "tool": "get_active_documents_metadata", "depends_on": []},
                {"id": "format_response", "tool": "response_formatter", "depends_on": ["fetch_metadata"]}
            ],
            "parallelizable": False,
            "estimated_steps": 2
        }
    else:
        dag = {
            "task_id": "general_query",
            "description": user_request,
            "nodes": [
                {"id": "query_documents", "tool": "aiagent", "depends_on": []},
                {"id": "format_response", "tool": "response_formatter", "depends_on": ["query_documents"]}
            ],
            "parallelizable": False,
            "estimated_steps": 2
        }

    return dag


def create_plan(user_request: str) -> str:
    """Create human-readable plan with DAG structure."""
    request_lower = user_request.lower()
    dag = create_dag(user_request)

    if "translate" in request_lower:
        steps = [
            "1. Identify target container",
            "2. Retrieve all active documents metadata",
            "3. Filter documents by requested category",
            "4. Validate document count",
            "5. Execute bulk translation with concurrency control",
            "6. Track progress and handle failures",
            "7. Return summary of successful and failed translations"
        ]
    elif "insight" in request_lower or "summarize" in request_lower or "summary" in request_lower:
        steps = [
            "1. Identify target container",
            "2. Retrieve document insights from database",
            "3. Filter by requested insight type",
            "4. Compile and format insights",
            "5. Return structured insight report"
        ]
    elif "how many" in request_lower or "count" in request_lower or "list" in request_lower:
        steps = [
            "1. Identify target container",
            "2. Call get_active_documents_metadata tool",
            "3. Count and filter documents",
            "4. Return document count and summary"
        ]
    elif "dashboard" in request_lower:
        steps = [
            "1. Identify target container",
            "2. Retrieve all document metadata",
            "3. Gather insights for all documents",
            "4. Generate structured HTML report",
            "5. Return downloadable dashboard"
        ]
    else:
        steps = [
            "1. Understand what the user is asking",
            "2. Identify the correct container",
            "3. Select the most appropriate tool",
            "4. Call the tool with correct parameters",
            "5. Format and return the result clearly"
        ]

    steps_text = "\n".join(steps)

    # Format DAG nodes
    dag_text = "\n".join([
        f"  [{n['id']}] → tool:{n['tool']} | deps:{n['depends_on'] or 'none'}"
        for n in dag["nodes"]
    ])

    plan = (
        f"\n=== AGENT PLAN ===\n"
        f"User Request: {user_request}\n\n"
        f"Execution Steps:\n{steps_text}\n\n"
        f"Execution DAG:\n{dag_text}\n"
        f"Parallelizable: {dag['parallelizable']}\n"
        f"==================\n"
    )
    return plan