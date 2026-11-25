# Vector Memory MCP (`vector-memory`)

Multi-user semantic + keyword hybrid vector memory MCP server (`Vector-Memory-Server`) exposing SSE on container port `8080` (host port `8089` via `docker-compose.yml`).

Uses per-user isolated SQLite databases (`<VECTOR_MEMORY_DATA_DIR>/users/<username>/memory.db`) with `sqlite-vec` cosine vector search, `FTS5` BM25 keyword search, Reciprocal Rank Fusion (RRF) + recency/importance boosting, and constant-time API key authentication (`Authorization: Bearer <key>`, `X-API-Key`, or `api_key` parameter). Supports local `fastembed` embeddings (default `BAAI/bge-small-en-v1.5`, 384-dim) or a remote OpenAI-compatible `/v1/embeddings` endpoint.

## Tools

All tools accept `api_key: str = ""` as an optional fallback when `Authorization: Bearer` or `X-API-Key` HTTP headers are not sent by the MCP client.

### `store_memory(content: str, namespace: str = "default", tags: str = "", source: str = "", importance: int = 3, ttl_days: int = 0, dedup_threshold: float = 0.92, api_key: str = "") -> str`
Store a semantic memory. Checks for near-duplicates in the same `namespace` and updates in place if cosine similarity >= `dedup_threshold` (set `0` to always insert). `importance` is clamped to `[1, 5]`; `ttl_days > 0` sets an expiration timestamp.

### `store_document(content: str, title: str = "", namespace: str = "default", tags: str = "", source: str = "", importance: int = 3, chunk_size: int = 800, chunk_overlap: int = 100, api_key: str = "") -> str`
Split a long document into overlapping chunks (`chunk_size` clamped to `[100, 4000]`), batch-embed them, and store them linked by a shared `doc_id`.

### `search_memories(query: str, namespace: str = "", tags: str = "", min_importance: int = 1, limit: int = 10, mode: str = "hybrid", include_expired: bool = False, api_key: str = "") -> str`
Search memories using `"hybrid"` (vector + FTS5 BM25 RRF), `"vector"`, or `"keyword"` mode (`limit` clamped to `[1, 50]`), with recency, importance, and access-count boosting.

### `list_memories(namespace: str = "", tags: str = "", include_deleted: bool = False, limit: int = 50, offset: int = 0, api_key: str = "") -> str`
List memories with optional `namespace`, `tags`, `include_deleted`, and pagination (`limit` clamped to `[1, 200]`, `offset >= 0`).

### `update_memory(memory_id: str, content: str = "", namespace: str = "", tags: str = "", importance: int = 0, api_key: str = "") -> str`
Update an existing memory's fields by `memory_id`. Automatically re-embeds if `content` changes.

### `delete_memory(memory_id: str, permanent: bool = False, api_key: str = "") -> str`
Soft-delete a memory to trash (`permanent=False`) or permanently erase it from DB, vector, and FTS5 tables (`permanent=True`).

### `restore_memory(memory_id: str, api_key: str = "") -> str`
Restore a soft-deleted memory from trash.

### `purge_trash(namespace: str = "", api_key: str = "") -> str`
Permanently delete all soft-deleted memories (optionally scoped to `namespace`).

### `get_memory_stats(api_key: str = "") -> str`
Return active count, trashed count, namespace breakdown, DB size in bytes, and embedding model/dimension config.

### `export_memories(namespace: str = "", format: str = "json", api_key: str = "") -> str`
Export active memories as `"json"` or `"markdown"`.

## Setup & Environment Variables

1. Create `vector-memory/api_keys.json` from `vector-memory/api_keys.example.json`:
   ```json
   [
     {
       "user": "carlos",
       "key": "replace-with-strong-secret-key"
     }
   ]
   ```
2. Key environment variables (configured in `docker-compose.yml`):
   - `VECTOR_MEMORY_DATA_DIR` (default `/app/data`)
   - `API_KEYS_FILE` (default `/app/api_keys.json`)
   - `EMBEDDING_BACKEND`: `"local"` (default, `fastembed`) or `"remote"`
   - `EMBEDDING_MODEL`: default `"BAAI/bge-small-en-v1.5"`
   - `EMBEDDING_DIM`: default `"384"` (must match model output dimension)
   - `FASTEMBED_CACHE_DIR`: default `"/app/data/models"`
   - `EMBEDDING_API_URL`: remote OpenAI-compatible endpoint (default `http://host.docker.internal:11434/v1/embeddings`)
   - `EMBEDDING_API_KEY`: optional bearer token for `remote` backend

## How to Run

### Docker Compose (Recommended)
From the repository root (after creating `vector-memory/api_keys.json`):
```bash
docker compose up -d --build vector-memory
```
SSE endpoint: `http://localhost:8089/sse`

### Standalone Docker
```bash
docker build -t walpaca-mcp-vector-memory ./vector-memory
docker run -d --name walpaca_mcp_vector_memory -p 8089:8080 \
  -v "$(pwd)/vector-memory/data:/app/data" \
  -v "$(pwd)/vector-memory/api_keys.json:/app/api_keys.json:ro" \
  walpaca-mcp-vector-memory
```

### Local Python
```bash
cd vector-memory
pip install -r requirements.txt
cp api_keys.example.json api_keys.json
python server.py
```
SSE endpoint: `http://localhost:8080/sse`

### Unit Tests
```bash
python3 -m unittest discover -s vector-memory -p "test_*.py"
```

## Configure in Other Tools

### Generic MCP Client (SSE with Header Auth)
- **Transport**: `sse`
- **URL**: `http://localhost:8089/sse`
- **Headers**: `Authorization: Bearer <your-api-key>` (or `X-API-Key: <your-api-key>`)

### JSON Client Config (Cursor / Windsurf / MCP-compatible clients)
```json
{
  "mcpServers": {
    "vector-memory": {
      "url": "http://localhost:8089/sse",
      "headers": {
        "Authorization": "Bearer replace-with-strong-secret-key"
      }
    }
  }
}
```

### Claude Desktop (via `mcp-remote` SSE bridge)
```json
{
  "mcpServers": {
    "vector-memory": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "http://localhost:8089/sse",
        "--header",
        "Authorization: Bearer replace-with-strong-secret-key"
      ]
    }
  }
}
```
*(If a client does not support custom SSE headers, pass `api_key` in tool calls instead.)*

## Usage Examples
- Index project docs or meeting notes with `store_document(..., namespace="project-atlas")` and query them semantically via `search_memories`.
- Store temporary reminders with `ttl_days=7` so expired items auto-prune.
- Isolate memories per user via `api_keys.json` and export backups with `export_memories(format="markdown")`.
