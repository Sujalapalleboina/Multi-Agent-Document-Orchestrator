import json
from typing import AsyncGenerator
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'mcp_server'))


async def generate_html_dashboard(container_id: str) -> AsyncGenerator[str, None]:
    """Generate a real HTML dashboard from document data."""

    from Sample_FastMCP import get_active_documents_metadata, get_document_insights

    yield f"event: update\ndata: [DashboardAgent] Fetching documents from {container_id}...\n\n"

    # Fetch all documents
    metadata = await get_active_documents_metadata(container_id=container_id)
    documents = metadata.get("documents", [])
    total = metadata.get("total_documents", 0)

    yield f"event: update\ndata: [DashboardAgent] Retrieved {total} documents\n\n"

    # Analyze categories
    categories = {}
    languages = {}
    statuses = {}

    for doc in documents:
        cat = doc.get("category", "unknown")
        lang = doc.get("language", "unknown")
        status = doc.get("status", "unknown")
        categories[cat] = categories.get(cat, 0) + 1
        languages[lang] = languages.get(lang, 0) + 1
        statuses[status] = statuses.get(status, 0) + 1

    yield f"event: update\ndata: [DashboardAgent] Analyzing document categories and metadata...\n\n"
    yield f"event: update\ndata: [DashboardAgent] Found {len(categories)} categories, {len(languages)} languages\n\n"
    yield f"event: update\ndata: [DashboardAgent] Generating HTML dashboard...\n\n"

    # Generate category bars
    category_bars = ""
    max_count = max(categories.values()) if categories else 1
    colors = ["#4F46E5", "#7C3AED", "#2563EB", "#0891B2", "#059669", "#D97706", "#DC2626"]
    for idx, (cat, count) in enumerate(sorted(categories.items(), key=lambda x: -x[1])):
        pct = (count / max_count) * 100
        color = colors[idx % len(colors)]
        category_bars += f"""
        <div class="bar-row">
            <div class="bar-label">{cat.title()}</div>
            <div class="bar-track">
                <div class="bar-fill" style="width:{pct}%;background:{color}"></div>
            </div>
            <div class="bar-count">{count:,}</div>
        </div>"""

    # Generate language rows
    language_rows = ""
    for lang, count in sorted(languages.items(), key=lambda x: -x[1])[:8]:
        pct = round((count / total) * 100, 1)
        language_rows += f"""
        <tr>
            <td>{lang.upper()}</td>
            <td>{count:,}</td>
            <td>{pct}%</td>
        </tr>"""

    # Generate status cards
    status_cards = ""
    status_colors = {"ACTIVE": "#059669", "PROCESSING": "#D97706", "ERROR": "#DC2626"}
    for status, count in statuses.items():
        color = status_colors.get(status, "#6B7280")
        status_cards += f"""
        <div class="status-card" style="border-left:4px solid {color}">
            <div class="status-count">{count:,}</div>
            <div class="status-label">{status}</div>
        </div>"""

    # Build full HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AICloudDrive Dashboard — {container_id}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #F3F4F6; color: #1F2937; }}
        .header {{ background: linear-gradient(135deg, #4F46E5, #7C3AED); color: white; padding: 32px 40px; }}
        .header h1 {{ font-size: 28px; font-weight: 700; }}
        .header p {{ opacity: 0.85; margin-top: 6px; font-size: 14px; }}
        .container {{ max-width: 1200px; margin: 32px auto; padding: 0 24px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 32px; }}
        .stat-card {{ background: white; border-radius: 12px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .stat-value {{ font-size: 36px; font-weight: 800; color: #4F46E5; }}
        .stat-label {{ font-size: 13px; color: #6B7280; margin-top: 4px; }}
        .section {{ background: white; border-radius: 12px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 24px; }}
        .section h2 {{ font-size: 18px; font-weight: 700; margin-bottom: 20px; color: #111827; }}
        .bar-row {{ display: flex; align-items: center; margin-bottom: 12px; gap: 12px; }}
        .bar-label {{ width: 120px; font-size: 13px; color: #374151; text-align: right; }}
        .bar-track {{ flex: 1; background: #F3F4F6; border-radius: 999px; height: 24px; overflow: hidden; }}
        .bar-fill {{ height: 100%; border-radius: 999px; transition: width 0.6s ease; }}
        .bar-count {{ width: 60px; font-size: 13px; font-weight: 600; color: #374151; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ text-align: left; padding: 10px 12px; background: #F9FAFB; font-size: 12px; color: #6B7280; text-transform: uppercase; letter-spacing: 0.05em; }}
        td {{ padding: 10px 12px; border-top: 1px solid #F3F4F6; font-size: 14px; }}
        .status-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }}
        .status-card {{ background: #F9FAFB; border-radius: 8px; padding: 16px; }}
        .status-count {{ font-size: 28px; font-weight: 700; color: #111827; }}
        .status-label {{ font-size: 12px; color: #6B7280; margin-top: 4px; text-transform: uppercase; }}
        .footer {{ text-align: center; padding: 24px; color: #9CA3AF; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>AICloudDrive Intelligence Dashboard</h1>
        <p>Container: {container_id} &nbsp;|&nbsp; Total Documents: {total:,} &nbsp;|&nbsp; Generated by AI Agent</p>
    </div>
    <div class="container">
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{total:,}</div>
                <div class="stat-label">Total Documents</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{len(categories)}</div>
                <div class="stat-label">Categories</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{len(languages)}</div>
                <div class="stat-label">Languages</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{len(statuses)}</div>
                <div class="stat-label">Status Types</div>
            </div>
        </div>

        <div class="section">
            <h2>Documents by Category</h2>
            {category_bars}
        </div>

        <div class="section">
            <h2>Documents by Language</h2>
            <table>
                <thead>
                    <tr><th>Language</th><th>Count</th><th>Percentage</th></tr>
                </thead>
                <tbody>
                    {language_rows}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>Document Status</h2>
            <div class="status-grid">
                {status_cards}
            </div>
        </div>
    </div>
    <div class="footer">Generated by AI Document Agent &nbsp;|&nbsp; {container_id}</div>
</body>
</html>"""

    # Save dashboard to file
    output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), f"dashboard_{container_id}.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    yield f"event: update\ndata: [DashboardAgent] Dashboard saved to dashboard_{container_id}.html\n\n"
    yield f"event: done\ndata: [DashboardAgent] HTML dashboard generated successfully! File: dashboard_{container_id}.html — Contains {total:,} documents across {len(categories)} categories and {len(languages)} languages.\n\n"