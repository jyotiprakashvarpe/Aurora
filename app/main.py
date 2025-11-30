from typing import List, Any, Dict
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import httpx
import logging

MESSAGES_API_URL = "https://november7-730026606190.europe-west1.run.app/messages/"

logger = logging.getLogger("uvicorn")
app = FastAPI(title="Message Search Service")

# In-memory cache of all messages
messages_cache: List[Dict[str, Any]] = []


class SearchResponse(BaseModel):
    query: str
    page: int
    page_size: int
    total: int
    total_pages: int
    results: List[Dict[str, Any]]


async def fetch_messages_from_source() -> List[Dict[str, Any]]:
    """
    Fetch all messages from the upstream /messages endpoint.
    The upstream returns: { "total": <int>, "items": [ ... ] }
    """
    logger.info("Fetching messages from upstream: %s", MESSAGES_API_URL)
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(MESSAGES_API_URL)
        resp.raise_for_status()
        data = resp.json()

        # The upstream API returns { "total": ..., "items": [...] }
        if isinstance(data, dict) and "items" in data:
            items = data["items"]
            logger.info("Upstream returned %d items", len(items))
            return items

        # Fallback: if it ever returns a raw list
        if isinstance(data, list):
            logger.info("Upstream returned list with %d items", len(data))
            return data

        logger.warning("Unexpected upstream format: %s", type(data))
        return []


@app.on_event("startup")
async def startup_event():
    """
    On startup, preload messages into memory for fast search.
    """
    global messages_cache
    logger.info("Startup: loading messages into cache...")
    try:
        messages_cache = await fetch_messages_from_source()
        logger.info("Startup: loaded %d messages into cache", len(messages_cache))
    except Exception as e:
        logger.exception("Failed to load messages on startup: %s", e)
        messages_cache = []


def record_matches_query(record: Dict[str, Any], q: str) -> bool:
    """
    Simple case-insensitive substring search across all values in a record.
    """
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
    q: str = Query("", description="Search query string"),
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size (max 100)"),
):
    """
    Search endpoint:
    - Ensures cache is loaded (fallback if startup didn't run properly)
    - Filters records by `q`
    - Returns paginated results
    """
    global messages_cache

    # 🔁 Fallback: if for some reason startup didn't populate the cache
    if not messages_cache:
        logger.warning("messages_cache is empty in /search, refetching from upstream...")
        try:
            messages_cache = await fetch_messages_from_source()
            logger.info("Fetched %d messages inside /search", len(messages_cache))
        except Exception as e:
            logger.exception("Failed to fetch messages in /search: %s", e)
            messages_cache = []

    # Now do the search
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
