from typing import List, Any, Dict
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import httpx
import logging

MESSAGES_API_URL = "https://november7-730026606190.europe-west1.run.app/messages"

logger = logging.getLogger("uvicorn")
app = FastAPI(title="Message Search Service")

messages_cache: List[Dict[str, Any]] = []  # in-memory store


class SearchResponse(BaseModel):
    query: str
    page: int
    page_size: int
    total: int
    total_pages: int
    results: List[Dict[str, Any]]

async def fetch_messages_from_source():
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(MESSAGES_API_URL)
        resp.raise_for_status()
        data = resp.json()

        # The upstream API returns { "total": ..., "items": [...] }
        if isinstance(data, dict) and "items" in data:
            return data["items"]

        # In case upstream returns a list (fallback)
        if isinstance(data, list):
            return data

        return []


@app.on_event("startup")
async def startup_event():
    global messages_cache
    try:
        messages_cache = await fetch_messages_from_source()
        logger.info("Loaded %d messages into cache", len(messages_cache))
    except Exception as e:
        logger.exception("Failed to load messages on startup: %s", e)
        messages_cache = []


def record_matches_query(record: Dict[str, Any], q: str) -> bool:
    if not q:
        return True
    q_lower = q.lower()
    for value in record.values():
        if value is None:
            continue
        if q_lower in str(value).lower():
            return True
    return False


@app.get("/search", response_model=SearchResponse)
async def search_messages(
    q: str = Query("", description="Search query"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    if messages_cache is None:
        raise HTTPException(status_code=500, detail="Messages not loaded")

    filtered = [m for m in messages_cache if record_matches_query(m, q)]
    total = len(filtered)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    if page > total_pages and total > 0:
        raise HTTPException(status_code=400, detail="Page number out of range")

    start = (page - 1) * page_size
    end = start + page_size
    results = filtered[start:end]

    return SearchResponse(
        query=q,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
        results=results,
    )

