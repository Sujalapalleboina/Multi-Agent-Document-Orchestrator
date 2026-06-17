"""
Run this script to create a sample database for testing.
Creates 2,500 documents per container = 10,000 total across 4 containers.
"""

import sqlite3
import json
import random
from pathlib import Path

DB_PATH = Path("mcp_server/fake_database.db")

CATEGORIES = ["financial", "legal", "business", "compliance", "hr", "meeting", "technical"]
LANGUAGES = ["en", "fr", "de", "es", "it", "pt", "ja", "zh", "nl", "ar", "ko", "ru"]
STATUSES = ["ACTIVE", "ACTIVE", "ACTIVE", "ACTIVE", "PROCESSING", "ERROR"]
CONTAINERS = ["container_001", "container_002", "container_003", "container_004"]

SAMPLE_NAMES = [
    "Annual Report 2024.pdf",
    "Legal Agreement.pdf",
    "HR Policy Manual.pdf",
    "Financial Statement Q4.pdf",
    "Board Meeting Minutes.pdf",
    "Compliance Report.pdf",
    "Technical Specification.pdf",
    "Business Proposal.pdf",
    "NDA Agreement.pdf",
    "Invoice Summary.pdf",
    "Merger Agreement.pdf",
    "Employee Handbook.pdf",
    "Risk Assessment.pdf",
    "Budget Forecast.pdf",
    "Project Charter.pdf"
]

SAMPLE_SUMMARIES = [
    "This document outlines the annual financial performance and strategic goals.",
    "A legal agreement between two parties covering terms and conditions.",
    "Company HR policies covering employee conduct and benefits.",
    "Quarterly financial statements showing revenue and expenses.",
    "Minutes from the board meeting covering key decisions.",
    "Compliance report covering regulatory requirements and audits.",
    "Technical specification for system architecture and implementation.",
    "Business proposal outlining project scope and deliverables.",
]

SAMPLE_KEYWORDS = [
    ["revenue", "profit", "growth", "annual"],
    ["contract", "agreement", "liability", "terms"],
    ["employee", "policy", "benefits", "conduct"],
    ["financial", "quarterly", "statement", "budget"],
    ["compliance", "regulatory", "audit", "risk"],
    ["technical", "architecture", "system", "implementation"],
    ["meeting", "minutes", "agenda", "decisions"],
    ["legal", "clause", "indemnity", "jurisdiction"],
]

def create_database():
    print(f"Creating sample database at {DB_PATH}...")

    if DB_PATH.exists():
        DB_PATH.unlink()
        print("Deleted old database — creating fresh one...")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE documents (
            content_id TEXT PRIMARY KEY,
            container_id TEXT,
            document_name TEXT,
            page_count INTEGER,
            size_bytes INTEGER,
            language TEXT,
            uploaded_at TEXT,
            status TEXT,
            category TEXT,
            classification_category TEXT,
            classification_subcategory TEXT,
            classification_confidence REAL,
            classification_document_type TEXT,
            summary TEXT,
            pii_data TEXT,
            pii_count INTEGER,
            keywords TEXT
        )
    """)

    total = 0
    for container in CONTAINERS:
        print(f"  Creating documents for {container}...")
        for i in range(1, 2501):
            doc_id = f"{container}_doc_{i:06d}"
            category = random.choice(CATEGORIES)
            language = random.choice(LANGUAGES)
            status = random.choice(STATUSES)
            name = random.choice(SAMPLE_NAMES)
            summary = random.choice(SAMPLE_SUMMARIES)
            keywords = random.choice(SAMPLE_KEYWORDS)

            cursor.execute("""
                INSERT INTO documents VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, (
                doc_id,
                container,
                name,
                random.randint(1, 100),
                random.randint(10000, 5000000),
                language,
                "2024-01-15T10:00:00Z",
                status,
                category,
                category,
                category + "_report",
                round(random.uniform(0.7, 0.99), 2),
                "document",
                summary,
                json.dumps(["John Doe", "jane@example.com"]),
                random.randint(0, 5),
                json.dumps(keywords)
            ))
            total += 1

        conn.commit()
        print(f"  {container} done — 2,500 documents added")

    conn.close()
    print(f"\nDone! Created {total} total documents across {len(CONTAINERS)} containers.")
    print(f"Database saved to: {DB_PATH}")

    # Show breakdown
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT category, COUNT(*) FROM documents WHERE container_id='container_001' GROUP BY category ORDER BY COUNT(*) DESC")
    print("\nContainer_001 breakdown by category:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} documents")
    conn.close()

if __name__ == "__main__":
    create_database()