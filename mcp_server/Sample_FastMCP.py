"""
MCP Server — AICloudDrive Tools

This implementation connects to the sample SQLite database
created by create_sample_db.py

Run first: python create_sample_db.py
Then start: fastmcp run mcp_server/Sample_FastMCP.py --transport sse --port 8000
"""

import sqlite3
import json
import asyncio
import random
from typing import Optional
from pathlib import Path
from fastmcp import FastMCP

mcp = FastMCP("AICloudDrive Tools")

DB_PATH = Path(__file__).parent / "fake_database.db"


def get_db():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. "
            f"Please run: python create_sample_db.py"
        )
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def validate_container(container_id: str) -> bool:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM documents WHERE container_id = ?", (container_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0


def get_all_containers():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT container_id FROM documents ORDER BY container_id")
    containers = [row[0] for row in cursor.fetchall()]
    conn.close()
    return containers


@mcp.tool(name="get_active_documents_metadata")
async def get_active_documents_metadata(container_id: str) -> dict:
    """
    Get all documents in a container.
    Returns document IDs, names, categories, languages and statuses.
    """
    if not validate_container(container_id):
        available = get_all_containers()
        raise ValueError(f"Container {container_id} not found. Available: {available}")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT content_id, document_name, page_count, size_bytes,
               language, uploaded_at, status, category
        FROM documents
        WHERE container_id = ?
        ORDER BY content_id
    """, (container_id,))
    rows = cursor.fetchall()
    conn.close()

    documents = []
    for row in rows:
        documents.append({
            "documentId": row[0],
            "documentName": row[1],
            "pageCount": row[2],
            "size": row[3],
            "language": row[4],
            "uploadedAt": row[5],
            "status": row[6],
            "category": row[7]
        })

    return {
        "container_id": container_id,
        "documents": documents,
        "total_documents": len(documents)
    }


@mcp.tool(name="translate_document_preserving_structure")
async def translate_document_preserving_structure(
    document_id,
    destinationLanguageThreeLetterCode: str,
    container_id: str
) -> dict:
    """
    Translate one or many documents to target language.
    Supports bulk mode — pass a list of document IDs.
    """
    if not validate_container(container_id):
        available = get_all_containers()
        raise ValueError(f"Container {container_id} not found. Available: {available}")

    is_bulk = isinstance(document_id, list)

    if not is_bulk:
        await asyncio.sleep(0.1)
        return {
            "status": "success",
            "output_path": f"https://storage.example.com/{document_id}_{destinationLanguageThreeLetterCode}.pdf",
            "message": f"Translation successful for {document_id}"
        }

    # Bulk mode
    successful = 0
    failed = 0
    failed_docs = []

    semaphore = asyncio.Semaphore(20)

    async def translate_one(doc_id):
        async with semaphore:
            await asyncio.sleep(0.05)
            if random.random() < 0.03:
                return False, doc_id
            return True, doc_id

    tasks = [translate_one(doc_id) for doc_id in document_id]
    results = []
    for i in range(0, len(tasks), 100):
        chunk = tasks[i:i+100]
        chunk_results = await asyncio.gather(*chunk)
        results.extend(chunk_results)

    for success, doc_id in results:
        if success:
            successful += 1
        else:
            failed += 1
            failed_docs.append(doc_id)

    return {
        "status": "success",
        "mode": "bulk",
        "successful": successful,
        "failed": failed,
        "total": len(document_id),
        "language": destinationLanguageThreeLetterCode,
        "failed_documents": failed_docs[:10],
        "message": f"Bulk translation complete: {successful} successful, {failed} failed"
    }


@mcp.tool(name="get_document_insights")
async def get_document_insights(
    container_id: str,
    model: Optional[str] = None
) -> dict:
    """
    Get AI insights for all documents in container.
    Includes classification, summarization, PII detection, keywords.
    """
    if not validate_container(container_id):
        available = get_all_containers()
        raise ValueError(f"Container {container_id} not found. Available: {available}")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT content_id, classification_category, summary,
               pii_data, pii_count, keywords
        FROM documents
        WHERE container_id = ?
        ORDER BY content_id
    """, (container_id,))
    rows = cursor.fetchall()
    conn.close()

    insights = {}
    for row in rows:
        doc_id = row[0]
        all_insights = [
            {
                "name": "CLASSIFICATION",
                "status": "SUCCESS",
                "data": {"category": row[1]},
                "error": None
            },
            {
                "name": "SUMMARIZATION",
                "status": "SUCCESS",
                "data": row[2],
                "error": None
            },
            {
                "name": "REDACTION",
                "status": "SUCCESS",
                "data": {
                    "pii_found": json.loads(row[3]),
                    "total_pii_count": row[4]
                },
                "error": None
            },
            {
                "name": "KEYWORDS",
                "status": "SUCCESS",
                "data": {"keywords": json.loads(row[5])},
                "error": None
            }
        ]
        if model:
            model_map = {
                "CLASSIFICATION": "CLASSIFICATION",
                "SUMMARISATION": "SUMMARIZATION",
                "SUMMARIZATION": "SUMMARIZATION",
                "REDACTION": "REDACTION",
                "KEYWORD": "KEYWORDS",
                "KEYWORDS": "KEYWORDS"
            }
            target = model_map.get(model.upper(), model.upper())
            all_insights = [i for i in all_insights if i["name"] == target]
        insights[doc_id] = all_insights

    return {
        "container_id": container_id,
        "total_documents": len(rows),
        "insights": insights
    }


@mcp.tool(name="aiagent")
async def aiagent(prompt: str, container_id: str) -> str:
    """
    RAG-based document Q&A.
    Searches document corpus and answers questions.
    """
    if not validate_container(container_id):
        available = get_all_containers()
        raise ValueError(f"Container {container_id} not found. Available: {available}")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM documents WHERE container_id = ?", (container_id,))
    doc_count = cursor.fetchone()[0]
    conn.close()

    prompt_lower = prompt.lower()

    if "how many" in prompt_lower or "count" in prompt_lower:
        return f"There are {doc_count} documents in {container_id}."
    elif "financial" in prompt_lower:
        return f"[{container_id} — {doc_count} docs] The financial documents contain revenue reports, expense statements, and budget forecasts."
    elif "legal" in prompt_lower:
        return f"[{container_id} — {doc_count} docs] The legal documents include NDA agreements, contracts, and compliance reports."
    elif "summar" in prompt_lower:
        return f"[{container_id} — {doc_count} docs] This container has {doc_count} documents across multiple categories including financial, legal, HR, and technical documents."
    else:
        return (
            f"[{container_id} — {doc_count} docs] "
            f"Based on the document corpus, here is information about '{prompt}': "
            f"The documents contain relevant information across {doc_count} files. "
            f"For more specific answers, please ask about a particular document category."
        )