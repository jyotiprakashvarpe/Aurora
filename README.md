# Message Search Engine

This project implements a **simple, fast search engine** on top of the November 7 data source.  
It exposes a clean, searchable API (`/search`) built on top of the upstream endpoint:

 **GET /messages**  
`https://november7-730026606190.europe-west1.run.app/docs#/default/get_messages_messages__get`

The goal is to provide a **publicly accessible**, **low-latency** (<100ms) search API using modern Python tooling.

---

# **Goal**

Build a simple search engine that:

1. Fetches data from the `/messages` endpoint.
2. Allows clients to perform full-text search.
3. Returns **paginated**, **filtered** results.
4. Runs in **Python (latest stable)** using any modern web framework.
5. Is **deployed publicly** and reachable via the internet.
6. Responds in **under 100ms**.

---

# **Solution Overview**

This service uses:

- **Python 3.12**
- **FastAPI**
- **Uvicorn** (ASGI server)
- **httpx** (async client)
- **Docker** (for consistent deployment)

###  How it works

1. On startup, the service fetches all messages from the upstream `/messages` endpoint.
2. All messages are stored **in memory**, enabling:
   - Very fast lookups
   - No repeated upstream calls
   - Predictable latency
3. The `/search` API endpoint:
   - Accepts `q`, `page`, `page_size`
   - Performs a simple case-insensitive substring search
   - Applies pagination
   - Returns structured output with metadata

This design ensures **consistently low latency** and **high availability**.

---

# **API Endpoints**

## **GET /search**

Search the cached messages for a query string.

### **Query Parameters**

| Parameter     | Type | Required | Default | Description |
|---------------|------|----------|----------|-------------|
| `q`           | str  | No       | `""`     | Query string to search for |
| `page`        | int  | No       | `1`      | Page number (1-based) |
| `page_size`   | int  | No       | `20`     | Number of items per page |

### **Example Request**

/search?q=test&page=1&page_size=20


### **Example Response**

```json
{
  "query": "test",
  "page": 1,
  "page_size": 20,
  "total": 42,
  "total_pages": 3,
  "results": [
    {
      "id": 123,
      "message": "This is a test message",
      "timestamp": "2024-11-01T10:00:00Z"
    }
  ]
}

## Public Deployment

The service is publicly available at:

👉 https://aurora-search-service.onrender.com/

Swagger UI:
👉 https://aurora-search-service.onrender.com/docs

Example request:
👉 https://aurora-search-service.onrender.com/search?q=test&page=1&page_size=20

Bonus 1: Design Notes – Alternative Approaches

While I implemented a simple in-memory search for this exercise, here are some alternatives I considered:

1. SQLite + Full-Text Search (FTS5)

Approach: On startup, fetch /messages, write them into an SQLite DB with an FTS5 virtual table, and run MATCH queries for search.

Pros:

Still embedded / lightweight.

Proper full-text ranking and querying.

Cons:

Slightly more complexity for schema management and updates.

Needs periodic syncing with /messages if the data changes.

2. External Search Engine (Elasticsearch / OpenSearch / Meilisearch)

Approach: Index messages into a dedicated search engine; /search just forwards the query and paginates results from there.

Pros:

Very powerful search (fuzzy matching, relevance, faceting, etc.).

Scales to large datasets.

Cons:

Requires extra infrastructure.

Higher operational overhead for this small task.

3. In-Memory Inverted Index

Approach: Build a token-based inverted index at startup:

Map token → list of message IDs

For a query, intersect posting lists and fetch documents.

Pros:

Very fast lookup, better than naïve O(N) scanning for larger datasets.

Still no external dependency.

Cons:

More code and complexity (tokenization, index building, updates).

Overkill unless message count is high.

4. On-Demand Proxy to /messages

Approach: Instead of caching, the /search endpoint directly calls GET /messages with query parameters and passes through the results.

Pros:

Very simple to implement, no local storage.

Cons:

Latency heavily depends on upstream.

Harder to guarantee < 100ms for every request.

Coupled to uptime/performance of the upstream service.

For this coding task, I chose in-memory caching + simple filtering because it gives:

Predictable low latency

Simplicity

Easy reasoning for performance/behavior


Bonus 2: Reducing Latency to ~30ms

Currently, the endpoint is designed to stay under 100ms by:

Keeping messages in memory

Doing a single-pass filter + simple pagination

To further reduce latency to ~30ms, I would:

1. Precompute an In-Memory Index

Build an inverted index at startup:

Tokenize message text into terms.

Maintain a mapping term -> [message_ids].

For a query:

Tokenize the query.

Lookup posting lists and intersect/union them.

Fetch messages by ID and paginate.

This changes search from O(N) over all messages to roughly O(K) over matched lists, significantly reducing work for common queries.

2. Limit and Optimize the Search Space

Only index and search in the most relevant fields, e.g.:

text, subject, sender, etc.

Avoid stringifying entire records.

Use lowercased precomputed tokens.

3. Keep the Service “Warm” and Close to Users

Deploy in a region close to the upstream and expected clients.

Ensure:

No cold starts (use always-on instances).

Adequate CPU so GC and Python overhead are minimal.

4. Use Efficient Data Structures

Use Python built-ins that are C-optimized:

dict, list, set for index structures.

Optionally use libraries like rapidfuzz for fast fuzzy matching
if needed (while still staying under 30ms for typical queries).

5. Benchmark and Tune

Use a small benchmarking script (e.g., locust or wrk) to:

Measure median and p95 latency.

Tune page size, index structures, and number of workers.

With these changes, for a typical dataset (tens of thousands of messages), it’s realistic to get median latencies in the 5–20ms range on a modest instance.
