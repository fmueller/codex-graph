from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from codex_graph.api.dependencies import get_database
from codex_graph.core.ports.database import GraphDatabase
from codex_graph.core.query import (
    query_language_distribution,
    query_node_type_counts,
    query_statistics,
)

router = APIRouter(tags=["statistics"])


@router.get("/statistics")
async def statistics(
    db: GraphDatabase = Depends(get_database),
) -> dict[str, Any]:
    """Aggregation endpoint: counts, language distribution, and node type breakdown."""
    await db.ensure_ready()
    stats = await query_statistics(db)
    langs = await query_language_distribution(db)
    node_types = await query_node_type_counts(db)
    return {
        "counts": stats,
        "languages": [{"language": lang, "count": count} for lang, count in langs],
        "node_types": [{"type": t, "count": c} for t, c in node_types],
    }
