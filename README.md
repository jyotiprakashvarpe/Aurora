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
```
## Public Deployment

The service is publicly available at:

 https://aurora-search-service.onrender.com/
Swagger UI:
 https://aurora-search-service.onrender.com/docs

Example request:
 https://aurora-search-service.onrender.com/search?q=test&page=1&page_size=20

## Bonus 1: Design Notes – Alternative Approaches

While this project uses a simple in-memory search approach, here are several alternative designs that were considered:

---

### 1. SQLite + Full-Text Search (FTS5)

**Approach:**  
On startup, fetch `/messages`, store the data inside an SQLite database using an FTS5 virtual table, and perform `MATCH` queries for search.

**Pros:**  
- Lightweight and embedded (no external service)  
- Provides proper full-text indexing and ranking  

**Cons:**  
- Requires schema setup and migration handling  
- Needs periodic syncing if the upstream data changes  

---

### 2. External Search Engine (Elasticsearch / OpenSearch / Meilisearch)

**Approach:**  
Index messages into a dedicated search engine. The `/search` endpoint simply forwards queries and paginates responses.

**Pros:**  
- Very powerful search capabilities (fuzzy matching, relevance scoring, faceting)  
- Scales easily for large datasets  

**Cons:**  
- Adds infrastructure and operational complexity  
- Overkill for a small coding assignment  

---

### 3. In-Memory Inverted Index

**Approach:**  
Build a token-based inverted index at startup.  
Example structure:

token → [list of message IDs]


Search would involve intersecting posting lists and retrieving corresponding records.

**Pros:**  
- Extremely fast lookups for larger datasets  
- No external dependencies  

**Cons:**  
- More complex to implement (tokenization, parsing, index building)  
- Excessive for datasets of only a few thousand records  

---

### 4. On-Demand Proxy to the Upstream `/messages` API

**Approach:**  
Skip caching entirely and call the upstream API directly on each `/search` request, filtering and paginating results locally.

**Pros:**  
- Simplest implementation  
- No local storage needed  

**Cons:**  
- Latency depends entirely on upstream performance  
- Hard to maintain <100ms latency consistently  
- Tight coupling to upstream uptime  

---

### Rationale for Choosing In-Memory Search

For this assignment, in-memory caching with simple filtering provides:

- Predictably low latency  
- Minimal architectural complexity  
- Zero external dependencies  
- Easy reasoning about performance and behavior  

---

## Bonus 2: Reducing Latency to Approximately 30ms

The current service maintains sub-100ms latency by caching messages in memory, performing a single-pass filter, and supporting simple pagination. To further reduce latency to around 30ms, the following optimizations can be applied:

---

### 1. Precompute an In-Memory Inverted Index

Build an index at startup by:

- Tokenizing message text into searchable terms  
- Mapping each term to the message IDs containing it  
- Lowercasing and normalizing tokens  

Searching then becomes:

- Tokenize the query  
- Look up posting lists  
- Intersect or merge results  
- Fetch message documents  

This reduces search complexity from O(N) to roughly O(K), where K is the number of matched items.

---

### 2. Restrict and Optimize the Search Space

Index only the relevant fields such as:

- `message`  
- `user_name`  
- `user_id`

Avoid searching through entire records, timestamps, or unnecessary JSON fields.

Store lowercased, pre-tokenized versions to avoid repeated computation.

---

### 3. Keep the Service Warm and Close to Users

Performance can be improved by:

- Using always-on instances to avoid cold starts  
- Deploying in a region close to clients and upstream API  
- Ensuring sufficient CPU resources so Python’s garbage collector and event loop do not cause delays  

---

### 4. Use Efficient Data Structures

Leverage optimized Python built-ins:

- `dict` for indexing  
- `list` for posting lists  
- `set` for fast intersections  

Optionally incorporate optimized libraries like `rapidfuzz` if fuzzy matching is desired without sacrificing performance.

---

### 5. Benchmark and Tune

Use load-testing tools such as:

- `wrk`  
- `locust`  
- `ab`

Measure:

- p50 median latency  
- p95 and p99 tail latencies  
- Impact of page size and filtering strategy  

With these improvements, it is realistic to achieve:

- 5–20ms median response times  
- 20–35ms high-percentile latencies  

for datasets of similar size.
