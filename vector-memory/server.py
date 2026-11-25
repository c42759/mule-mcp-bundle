import asyncio
import contextvars
import hmac
import json
import os
import re
import sqlite3
import struct
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import sqlite_vec
import uvicorn
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server (container-internal SSE port 8080)
# TODO(security): Binds 0.0.0.0 inside container for Docker bridge port forwarding; restrict host exposure via docker-compose port mapping.
mcp = FastMCP("Vector-Memory-Server", host="0.0.0.0", port=8080)

DATA_DIR = Path(
    os.environ.get("VECTOR_MEMORY_DATA_DIR", Path(__file__).resolve().parent / "data")
).resolve()
API_KEYS_FILE = Path(
    os.environ.get("API_KEYS_FILE", Path(__file__).resolve().parent / "api_keys.json")
).resolve()

EMBEDDING_BACKEND = os.environ.get("EMBEDDING_BACKEND", "local").strip().lower()
EMBEDDING_API_URL = os.environ.get(
    "EMBEDDING_API_URL", "http://host.docker.internal:11434/v1/embeddings"
).strip()
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5").strip()
EMBEDDING_API_KEY = os.environ.get("EMBEDDING_API_KEY", "").strip()
EMBEDDING_DIM = max(1, int(os.environ.get("EMBEDDING_DIM", "384")))
FASTEMBED_CACHE_DIR = Path(
    os.environ.get("FASTEMBED_CACHE_DIR", str(DATA_DIR / "models"))
).resolve()

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
NAMESPACE_RE = re.compile(r"^[a-zA-Z0-9_.-]{1,64}$")

_HEADER_API_KEY: contextvars.ContextVar[str] = contextvars.ContextVar(
    "vector_memory_header_api_key", default=""
)
_REGISTRY_LOCK = threading.Lock()
_USER_LOCKS: dict[str, threading.Lock] = {}
_EMBEDDER_LOCK = threading.Lock()
_LOCAL_EMBEDDER = None


class ApiKeyHeaderMiddleware:
    """Extract Authorization Bearer or X-API-Key header into a per-request ContextVar."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        token_key = ""
        for name, value in scope.get("headers", []):
            lname = name.lower()
            if lname == b"authorization":
                raw = value.decode("latin-1").strip()
                if raw.lower().startswith("bearer "):
                    token_key = raw[7:].strip()
                    break
            elif lname == b"x-api-key" and not token_key:
                token_key = value.decode("latin-1").strip()

        ctx_token = _HEADER_API_KEY.set(token_key)
        try:
            await self.app(scope, receive, send)
        finally:
            _HEADER_API_KEY.reset(ctx_token)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_user_lock(username: str) -> threading.Lock:
    with _REGISTRY_LOCK:
        lock = _USER_LOCKS.get(username)
        if lock is None:
            lock = threading.Lock()
            _USER_LOCKS[username] = lock
        return lock


def load_api_keys(keys_path: Path | None = None) -> list[tuple[str, str]]:
    """Load and validate [{"user": "...", "key": "..."}] entries from JSON."""
    target = keys_path or API_KEYS_FILE
    if not target.exists():
        raise RuntimeError(
            f"API keys file not found at '{target}'. Configure API_KEYS_FILE or mount api_keys.json."
        )

    raw = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("API keys JSON root must be a list of {'user', 'key'} objects.")

    entries: list[tuple[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        user = str(item.get("user") or "").strip().lower()
        key = str(item.get("key") or "").strip()
        if not user or not key:
            continue
        if not USERNAME_RE.match(user):
            raise ValueError(f"Invalid username '{user}' in api_keys.json.")
        entries.append((user, key))

    if not entries:
        raise RuntimeError("No valid user/key entries found in api_keys.json.")
    return entries


def authenticate_user(api_key: str = "") -> str:
    """Resolve and verify API key (header preferred, tool parameter fallback) in constant time."""
    candidate = (_HEADER_API_KEY.get() or "").strip() or (api_key or "").strip()
    if not candidate:
        raise PermissionError(
            "Authentication required: provide Authorization Bearer / X-API-Key header or api_key parameter."
        )

    entries = load_api_keys()
    matched_user = ""
    for user, valid_key in entries:
        if hmac.compare_digest(candidate, valid_key):
            matched_user = user

    if not matched_user:
        raise PermissionError("Authentication failed: invalid API key.")
    return matched_user


def get_user_db_path(username: str) -> Path:
    """Return isolated SQLite DB path for `username`, strictly contained under DATA_DIR."""
    clean_user = (username or "").strip().lower()
    if not USERNAME_RE.match(clean_user):
        raise ValueError("Invalid username.")
    users_root = (DATA_DIR / "users").resolve()
    db_path = (users_root / clean_user / "memory.db").resolve()
    if users_root not in db_path.parents:
        raise ValueError("Security violation: resolved user DB path escapes DATA_DIR.")
    return db_path


def _normalize_namespace(namespace: str) -> str:
    ns = (namespace or "default").strip().lower()
    if not ns:
        return "default"
    if not NAMESPACE_RE.match(ns):
        raise ValueError(
            "Invalid namespace. Use 1-64 alphanumeric, underscore, hyphen, or dot characters."
        )
    return ns


def _parse_tags(raw_tags: str) -> list[str]:
    text = (raw_tags or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return sorted({str(t).strip().lower() for t in parsed if str(t).strip()})
        except json.JSONDecodeError:
            pass
    return sorted({part.strip().lower() for part in text.split(",") if part.strip()})


def _pack_vector(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _get_local_embedder():
    """Lazy-initialize and cache the local fastembed ONNX TextEmbedding model."""
    global _LOCAL_EMBEDDER
    with _EMBEDDER_LOCK:
        if _LOCAL_EMBEDDER is None:
            from fastembed import TextEmbedding

            FASTEMBED_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            _LOCAL_EMBEDDER = TextEmbedding(
                model_name=EMBEDDING_MODEL,
                cache_dir=str(FASTEMBED_CACHE_DIR),
            )
        return _LOCAL_EMBEDDER


def _embed_local_sync(texts: list[str]) -> list[list[float]]:
    embedder = _get_local_embedder()
    vectors: list[list[float]] = []
    for vec in embedder.embed(texts):
        floats = [float(x) for x in vec.tolist()]
        if len(floats) != EMBEDDING_DIM:
            raise ValueError(
                f"Embedding dimension mismatch: expected {EMBEDDING_DIM}, got {len(floats)}."
            )
        vectors.append(floats)
    return vectors


async def _embed_remote(texts: list[str]) -> list[list[float]]:
    if not EMBEDDING_API_URL:
        raise RuntimeError("EMBEDDING_API_URL is not configured.")

    headers = {"Content-Type": "application/json"}
    if EMBEDDING_API_KEY:
        headers["Authorization"] = f"Bearer {EMBEDDING_API_KEY}"

    payload = {"model": EMBEDDING_MODEL, "input": texts}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(EMBEDDING_API_URL, json=payload, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Embedding API returned HTTP {resp.status_code}: {resp.text[:300]}"
            )
        body = resp.json()

    data = body.get("data")
    if not isinstance(data, list) or len(data) != len(texts):
        raise RuntimeError("Unexpected embedding API response format.")

    # OpenAI-compatible responses include an index field
    ordered = sorted(data, key=lambda item: item.get("index", 0))
    vectors: list[list[float]] = []
    for item in ordered:
        emb = item.get("embedding")
        if not isinstance(emb, list) or len(emb) != EMBEDDING_DIM:
            got = len(emb) if isinstance(emb, list) else "invalid"
            raise ValueError(
                f"Embedding dimension mismatch: expected {EMBEDDING_DIM}, got {got}."
            )
        vectors.append([float(x) for x in emb])
    return vectors


async def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embedding vectors via local fastembed (default) or remote OpenAI-compatible API."""
    if not texts:
        return []
    if EMBEDDING_BACKEND == "local":
        return await asyncio.to_thread(_embed_local_sync, texts)
    if EMBEDDING_BACKEND == "remote":
        return await _embed_remote(texts)
    raise ValueError(
        f"Unsupported EMBEDDING_BACKEND '{EMBEDDING_BACKEND}'. Use 'local' or 'remote'."
    )


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            namespace TEXT NOT NULL DEFAULT 'default',
            doc_id TEXT,
            chunk_index INTEGER NOT NULL DEFAULT 0,
            content TEXT NOT NULL,
            tags TEXT NOT NULL DEFAULT '[]',
            source TEXT NOT NULL DEFAULT '',
            importance INTEGER NOT NULL DEFAULT 3,
            access_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_accessed_at TEXT,
            expires_at TEXT,
            deleted_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_memories_ns_del
            ON memories(namespace, deleted_at);

        CREATE VIRTUAL TABLE IF NOT EXISTS memories_vec USING vec0(
            memory_id TEXT PRIMARY KEY,
            embedding float[{EMBEDDING_DIM}] distance_metric=cosine
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
            memory_id UNINDEXED,
            content,
            tags,
            namespace
        );
        """
    )


def _open_user_db(username: str) -> sqlite3.Connection:
    db_path = get_user_db_path(username)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    _init_schema(conn)
    return conn


def _prune_expired(conn: sqlite3.Connection) -> int:
    now = _now_iso()
    rows = conn.execute(
        "SELECT id FROM memories WHERE expires_at IS NOT NULL AND expires_at <= ?",
        (now,),
    ).fetchall()
    if not rows:
        return 0
    ids = [r["id"] for r in rows]
    placeholders = ",".join("?" for _ in ids)
    conn.execute(f"DELETE FROM memories_vec WHERE memory_id IN ({placeholders})", ids)
    conn.execute(f"DELETE FROM memories_fts WHERE memory_id IN ({placeholders})", ids)
    conn.execute(f"DELETE FROM memories WHERE id IN ({placeholders})", ids)
    return len(ids)


def _insert_memory_row(
    conn: sqlite3.Connection,
    memory_id: str,
    namespace: str,
    content: str,
    vector: list[float],
    tags: list[str],
    source: str,
    importance: int,
    expires_at: str | None,
    doc_id: str | None = None,
    chunk_index: int = 0,
) -> None:
    now = _now_iso()
    tags_json = json.dumps(tags)
    tags_text = " ".join(tags)
    conn.execute(
        """
        INSERT INTO memories (
            id, namespace, doc_id, chunk_index, content, tags, source,
            importance, access_count, created_at, updated_at, expires_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
        """,
        (
            memory_id,
            namespace,
            doc_id,
            chunk_index,
            content,
            tags_json,
            source,
            importance,
            now,
            now,
            expires_at,
        ),
    )
    conn.execute(
        "INSERT INTO memories_vec (memory_id, embedding) VALUES (?, ?)",
        (memory_id, _pack_vector(vector)),
    )
    conn.execute(
        "INSERT INTO memories_fts (memory_id, content, tags, namespace) VALUES (?, ?, ?, ?)",
        (memory_id, content, tags_text, namespace),
    )


def _find_duplicate(
    conn: sqlite3.Connection,
    namespace: str,
    vector: list[float],
    threshold: float,
) -> tuple[str, float] | None:
    if threshold <= 0.0:
        return None
    rows = conn.execute(
        """
        SELECT v.memory_id, v.distance
        FROM memories_vec v
        JOIN memories m ON m.id = v.memory_id
        WHERE v.embedding MATCH ? AND v.k = 5
          AND m.namespace = ? AND m.deleted_at IS NULL
        ORDER BY v.distance ASC
        """,
        (_pack_vector(vector), namespace),
    ).fetchall()
    for row in rows:
        similarity = 1.0 - float(row["distance"])
        if similarity >= threshold:
            return row["memory_id"], similarity
    return None


def _chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    clean = (text or "").strip()
    if not clean:
        return []
    size = max(100, min(4000, int(chunk_size)))
    overlap = max(0, min(size // 2, int(chunk_overlap)))
    if len(clean) <= size:
        return [clean]

    chunks: list[str] = []
    start = 0
    step = size - overlap
    while start < len(clean):
        end = min(len(clean), start + size)
        chunks.append(clean[start:end].strip())
        if end >= len(clean):
            break
        start += step
    return [c for c in chunks if c]


def _build_fts_query(query: str) -> str:
    tokens = re.findall(r"[a-zA-Z0-9_]+", query or "")
    if not tokens:
        return ""
    return " OR ".join(f'"{tok}"' for tok in tokens[:20])


def _recency_boost(created_at_iso: str, access_count: int, importance: int) -> float:
    try:
        created = datetime.fromisoformat(created_at_iso)
        age_days = max(0.0, (datetime.now(timezone.utc) - created).total_seconds() / 86400.0)
    except Exception:
        age_days = 30.0
    recency = 1.0 / (1.0 + age_days / 30.0)
    imp_norm = max(1, min(5, int(importance))) / 5.0
    acc_norm = min(1.0, int(access_count) / 10.0)
    return 0.15 * recency + 0.10 * imp_norm + 0.05 * acc_norm


@mcp.tool()
async def store_memory(
    content: str,
    namespace: str = "default",
    tags: str = "",
    source: str = "",
    importance: int = 3,
    ttl_days: int = 0,
    dedup_threshold: float = 0.92,
    api_key: str = "",
) -> str:
    """
    Store a semantic memory in the authenticated user's isolated `sqlite-vec` + `FTS5` database.

    Generates an embedding via the configured OpenAI-compatible endpoint, checks for near-duplicate
    memories in the same namespace (updating in place when cosine similarity >= `dedup_threshold`),
    and indexes the content for hybrid semantic + keyword search.

    Args:
        content: Text fact, note, or preference to remember (e.g., "User prefers Neovim for Python").
        namespace: Logical collection inside the user's DB (default "default"; e.g., "project-atlas").
        tags: Optional comma-separated or JSON tags (e.g., "editor,python").
        source: Optional origin label (e.g., "chat", "docs").
        importance: Priority score clamped to [1, 5] (default 3).
        ttl_days: Optional expiration in days; 0 means never expires (default 0).
        dedup_threshold: Cosine similarity threshold in [0.0, 1.0] to upsert near-duplicates (default 0.92;
            set 0 to always insert a new record).
        api_key: Optional API key fallback if not passed via Authorization / X-API-Key header.
    """
    try:
        user = authenticate_user(api_key)
        text = (content or "").strip()
        if not text:
            return "Error storing memory: 'content' cannot be empty."

        ns = _normalize_namespace(namespace)
        tag_list = _parse_tags(tags)
        imp = max(1, min(5, int(importance)))
        ttl = max(0, int(ttl_days))
        expires_at = (
            (datetime.now(timezone.utc) + timedelta(days=ttl)).isoformat()
            if ttl > 0
            else None
        )
        threshold = max(0.0, min(1.0, float(dedup_threshold)))
        vector = (await get_embeddings([text]))[0]

        with _get_user_lock(user):
            conn = _open_user_db(user)
            try:
                with conn:
                    _prune_expired(conn)
                    dup = _find_duplicate(conn, ns, vector, threshold)
                    if dup is not None:
                        existing_id, sim = dup
                        now = _now_iso()
                        conn.execute(
                            """
                            UPDATE memories
                            SET content = ?, tags = ?, source = ?, importance = ?,
                                updated_at = ?, expires_at = ?
                            WHERE id = ?
                            """,
                            (text, json.dumps(tag_list), source.strip(), imp, now, expires_at, existing_id),
                        )
                        conn.execute("DELETE FROM memories_vec WHERE memory_id = ?", (existing_id,))
                        conn.execute(
                            "INSERT INTO memories_vec (memory_id, embedding) VALUES (?, ?)",
                            (existing_id, _pack_vector(vector)),
                        )
                        conn.execute("DELETE FROM memories_fts WHERE memory_id = ?", (existing_id,))
                        conn.execute(
                            "INSERT INTO memories_fts (memory_id, content, tags, namespace) VALUES (?, ?, ?, ?)",
                            (existing_id, text, " ".join(tag_list), ns),
                        )
                        return (
                            f"Updated existing near-duplicate memory (similarity={sim:.3f}):\n"
                            f"- ID: {existing_id}\n- User: {user}\n- Namespace: {ns}"
                        )

                    mem_id = str(uuid.uuid4())
                    _insert_memory_row(
                        conn=conn,
                        memory_id=mem_id,
                        namespace=ns,
                        content=text,
                        vector=vector,
                        tags=tag_list,
                        source=source.strip(),
                        importance=imp,
                        expires_at=expires_at,
                    )
                    return (
                        f"Stored memory:\n- ID: {mem_id}\n- User: {user}\n"
                        f"- Namespace: {ns}\n- Importance: {imp}"
                    )
            finally:
                conn.close()
    except Exception as e:
        return f"Error storing memory: {str(e)}"


@mcp.tool()
async def store_document(
    content: str,
    title: str = "",
    namespace: str = "default",
    tags: str = "",
    source: str = "",
    importance: int = 3,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
    api_key: str = "",
) -> str:
    """
    Split a long document or note into overlapping chunks, batch-embed them, and store them linked
    by a shared `doc_id` in the authenticated user's database.

    Args:
        content: Full text of the document or note to index.
        title: Optional title prefixed to each chunk for better semantic context.
        namespace: Logical collection inside the user's DB (default "default").
        tags: Optional comma-separated or JSON tags.
        source: Optional origin label (e.g., "guide.md").
        importance: Priority score clamped to [1, 5] (default 3).
        chunk_size: Maximum characters per chunk, clamped to [100, 4000] (default 800).
        chunk_overlap: Overlap characters between consecutive chunks (default 100).
        api_key: Optional API key fallback if not passed via Authorization / X-API-Key header.
    """
    try:
        user = authenticate_user(api_key)
        ns = _normalize_namespace(namespace)
        tag_list = _parse_tags(tags)
        imp = max(1, min(5, int(importance)))
        raw_chunks = _chunk_text(content, chunk_size, chunk_overlap)
        if not raw_chunks:
            return "Error storing document: 'content' cannot be empty."

        clean_title = (title or "").strip()
        chunks = [f"[{clean_title}] {c}" if clean_title else c for c in raw_chunks]
        vectors = await get_embeddings(chunks)
        doc_id = str(uuid.uuid4())

        with _get_user_lock(user):
            conn = _open_user_db(user)
            try:
                with conn:
                    _prune_expired(conn)
                    for idx, (chunk_text, vec) in enumerate(zip(chunks, vectors)):
                        _insert_memory_row(
                            conn=conn,
                            memory_id=str(uuid.uuid4()),
                            namespace=ns,
                            content=chunk_text,
                            vector=vec,
                            tags=tag_list,
                            source=source.strip(),
                            importance=imp,
                            expires_at=None,
                            doc_id=doc_id,
                            chunk_index=idx,
                        )
            finally:
                conn.close()

        return (
            f"Stored document '{clean_title or doc_id}' as {len(chunks)} chunk(s):\n"
            f"- Doc ID: {doc_id}\n- User: {user}\n- Namespace: {ns}"
        )
    except Exception as e:
        return f"Error storing document: {str(e)}"


@mcp.tool()
async def search_memories(
    query: str,
    namespace: str = "",
    tags: str = "",
    min_importance: int = 1,
    limit: int = 10,
    mode: str = "hybrid",
    include_expired: bool = False,
    api_key: str = "",
) -> str:
    """
    Search the authenticated user's isolated vector memory using hybrid (semantic + FTS5 BM25),
    vector-only, or keyword-only retrieval with recency and importance boosting.

    Args:
        query: Natural-language question or keywords (e.g., "preferred python editor").
        namespace: Optional namespace filter; empty searches all namespaces for this user.
        tags: Optional comma-separated tag filter (all specified tags must match).
        min_importance: Minimum importance [1, 5] (default 1).
        limit: Maximum results to return, clamped to [1, 50] (default 10).
        mode: Search mode: "hybrid" (default), "vector", or "keyword".
        include_expired: If True, skip automatic pruning of expired entries on this read (default False).
        api_key: Optional API key fallback if not passed via Authorization / X-API-Key header.
    """
    try:
        user = authenticate_user(api_key)
        q_clean = (query or "").strip()
        if not q_clean:
            return "Error searching memories: 'query' cannot be empty."

        ns_filter = _normalize_namespace(namespace) if (namespace or "").strip() else ""
        req_tags = _parse_tags(tags)
        min_imp = max(1, min(5, int(min_importance)))
        max_results = max(1, min(50, int(limit)))
        search_mode = (mode or "hybrid").strip().lower()
        if search_mode not in ("hybrid", "vector", "keyword"):
            return "Error searching memories: 'mode' must be 'hybrid', 'vector', or 'keyword'."

        q_vec = (await get_embeddings([q_clean]))[0] if search_mode in ("hybrid", "vector") else None

        with _get_user_lock(user):
            conn = _open_user_db(user)
            try:
                if not include_expired:
                    with conn:
                        _prune_expired(conn)

                scores: dict[str, float] = {}
                rows_by_id: dict[str, sqlite3.Row] = {}
                fetch_k = min(200, max_results * 5)

                if q_vec is not None:
                    vec_rows = conn.execute(
                        """
                        SELECT m.*, v.distance
                        FROM memories_vec v
                        JOIN memories m ON m.id = v.memory_id
                        WHERE v.embedding MATCH ? AND v.k = ?
                          AND m.deleted_at IS NULL AND m.importance >= ?
                        ORDER BY v.distance ASC
                        """,
                        (_pack_vector(q_vec), fetch_k, min_imp),
                    ).fetchall()
                    rank = 0
                    for r in vec_rows:
                        if ns_filter and r["namespace"] != ns_filter:
                            continue
                        row_tags = set(json.loads(r["tags"] or "[]"))
                        if req_tags and not set(req_tags).issubset(row_tags):
                            continue
                        rank += 1
                        rows_by_id[r["id"]] = r
                        sim = max(0.0, 1.0 - float(r["distance"]))
                        scores[r["id"]] = scores.get(r["id"], 0.0) + (1.0 / (60 + rank)) + 0.5 * sim

                if search_mode in ("hybrid", "keyword"):
                    fts_q = _build_fts_query(q_clean)
                    if fts_q:
                        fts_rows = conn.execute(
                            """
                            SELECT m.*, bm25(memories_fts) AS bm25_score
                            FROM memories_fts f
                            JOIN memories m ON m.id = f.memory_id
                            WHERE memories_fts MATCH ?
                              AND m.deleted_at IS NULL AND m.importance >= ?
                            ORDER BY bm25_score ASC
                            LIMIT ?
                            """,
                            (fts_q, min_imp, fetch_k),
                        ).fetchall()
                        rank = 0
                        for r in fts_rows:
                            if ns_filter and r["namespace"] != ns_filter:
                                continue
                            row_tags = set(json.loads(r["tags"] or "[]"))
                            if req_tags and not set(req_tags).issubset(row_tags):
                                continue
                            rank += 1
                            rows_by_id[r["id"]] = r
                            scores[r["id"]] = scores.get(r["id"], 0.0) + (1.0 / (60 + rank))

                if not rows_by_id:
                    return f"No matching memories found for user '{user}'."

                ranked = []
                for mem_id, base_score in scores.items():
                    r = rows_by_id[mem_id]
                    total = base_score + _recency_boost(
                        r["created_at"], r["access_count"], r["importance"]
                    )
                    ranked.append((total, r))
                ranked.sort(key=lambda item: -item[0])
                top = ranked[:max_results]

                now = _now_iso()
                with conn:
                    for _, r in top:
                        conn.execute(
                            "UPDATE memories SET access_count = access_count + 1, last_accessed_at = ? WHERE id = ?",
                            (now, r["id"]),
                        )

                lines = [f"Found {len(top)} memory result(s) for user '{user}' (mode={search_mode}):"]
                for idx, (score, r) in enumerate(top, start=1):
                    tag_str = ", ".join(json.loads(r["tags"] or "[]")) or "none"
                    lines.append(
                        f"{idx}. [{r['id']}] (score={score:.3f}, ns={r['namespace']}, imp={r['importance']}, tags={tag_str})\n"
                        f"   {r['content']}"
                    )
                return "\n".join(lines)
            finally:
                conn.close()
    except Exception as e:
        return f"Error searching memories: {str(e)}"


@mcp.tool()
async def list_memories(
    namespace: str = "",
    tags: str = "",
    include_deleted: bool = False,
    limit: int = 50,
    offset: int = 0,
    api_key: str = "",
) -> str:
    """
    List memories for the authenticated user with optional namespace, tag, and trash filters.

    Args:
        namespace: Optional namespace filter.
        tags: Optional comma-separated tags filter.
        include_deleted: Include soft-deleted memories when True (default False).
        limit: Maximum entries to return, clamped to [1, 200] (default 50).
        offset: Pagination offset (default 0).
        api_key: Optional API key fallback if not passed via Authorization / X-API-Key header.
    """
    try:
        user = authenticate_user(api_key)
        ns_filter = _normalize_namespace(namespace) if (namespace or "").strip() else ""
        req_tags = _parse_tags(tags)
        lim = max(1, min(200, int(limit)))
        off = max(0, int(offset))

        with _get_user_lock(user):
            conn = _open_user_db(user)
            try:
                with conn:
                    _prune_expired(conn)

                clauses = [] if include_deleted else ["deleted_at IS NULL"]
                params: list = []
                if ns_filter:
                    clauses.append("namespace = ?")
                    params.append(ns_filter)

                where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""
                rows = conn.execute(
                    f"SELECT * FROM memories {where_sql} ORDER BY updated_at DESC",
                    params,
                ).fetchall()

                filtered = []
                for r in rows:
                    row_tags = set(json.loads(r["tags"] or "[]"))
                    if req_tags and not set(req_tags).issubset(row_tags):
                        continue
                    filtered.append(r)

                page = filtered[off : off + lim]
                if not page:
                    return f"No memories found for user '{user}'."

                lines = [f"Showing {len(page)} of {len(filtered)} memory item(s) for user '{user}':"]
                for r in page:
                    status = " [TRASH]" if r["deleted_at"] else ""
                    tag_str = ", ".join(json.loads(r["tags"] or "[]")) or "none"
                    lines.append(
                        f"- [{r['id']}]{status} ns={r['namespace']} imp={r['importance']} tags={tag_str}: {r['content']}"
                    )
                return "\n".join(lines)
            finally:
                conn.close()
    except Exception as e:
        return f"Error listing memories: {str(e)}"


@mcp.tool()
async def update_memory(
    memory_id: str,
    content: str = "",
    namespace: str = "",
    tags: str = "",
    importance: int = 0,
    api_key: str = "",
) -> str:
    """
    Update an existing memory's content, namespace, tags, or importance for the authenticated user.
    Re-embeds automatically if `content` is changed.

    Args:
        memory_id: UUID of the memory to update.
        content: New text content (leave empty to keep existing).
        namespace: New namespace (leave empty to keep existing).
        tags: New comma-separated or JSON tags (leave empty to keep existing).
        importance: New importance 1–5 (0 keeps existing).
        api_key: Optional API key fallback if not passed via Authorization / X-API-Key header.
    """
    try:
        user = authenticate_user(api_key)
        target_id = (memory_id or "").strip()
        if not target_id:
            return "Error updating memory: 'memory_id' cannot be empty."

        new_content = (content or "").strip()
        new_vector = (await get_embeddings([new_content]))[0] if new_content else None

        with _get_user_lock(user):
            conn = _open_user_db(user)
            try:
                row = conn.execute(
                    "SELECT * FROM memories WHERE id = ?", (target_id,)
                ).fetchone()
                if row is None:
                    return f"Memory '{target_id}' not found for user '{user}'."

                final_content = new_content or row["content"]
                final_ns = _normalize_namespace(namespace) if (namespace or "").strip() else row["namespace"]
                final_tags = _parse_tags(tags) if (tags or "").strip() else json.loads(row["tags"] or "[]")
                final_imp = max(1, min(5, int(importance))) if int(importance) > 0 else row["importance"]
                now = _now_iso()

                with conn:
                    conn.execute(
                        """
                        UPDATE memories
                        SET content = ?, namespace = ?, tags = ?, importance = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (final_content, final_ns, json.dumps(final_tags), final_imp, now, target_id),
                    )
                    if new_vector is not None:
                        conn.execute("DELETE FROM memories_vec WHERE memory_id = ?", (target_id,))
                        conn.execute(
                            "INSERT INTO memories_vec (memory_id, embedding) VALUES (?, ?)",
                            (target_id, _pack_vector(new_vector)),
                        )
                    conn.execute("DELETE FROM memories_fts WHERE memory_id = ?", (target_id,))
                    conn.execute(
                        "INSERT INTO memories_fts (memory_id, content, tags, namespace) VALUES (?, ?, ?, ?)",
                        (target_id, final_content, " ".join(final_tags), final_ns),
                    )
                return f"Updated memory '{target_id}' for user '{user}'."
            finally:
                conn.close()
    except Exception as e:
        return f"Error updating memory: {str(e)}"


@mcp.tool()
async def delete_memory(
    memory_id: str,
    permanent: bool = False,
    api_key: str = "",
) -> str:
    """
    Soft-delete a memory (moving it to trash) or permanently delete it for the authenticated user.

    Args:
        memory_id: UUID of the memory to delete.
        permanent: If True, permanently erase from DB and vector/FTS indexes (default False).
        api_key: Optional API key fallback if not passed via Authorization / X-API-Key header.
    """
    try:
        user = authenticate_user(api_key)
        target_id = (memory_id or "").strip()
        if not target_id:
            return "Error deleting memory: 'memory_id' cannot be empty."

        with _get_user_lock(user):
            conn = _open_user_db(user)
            try:
                row = conn.execute(
                    "SELECT id, deleted_at FROM memories WHERE id = ?", (target_id,)
                ).fetchone()
                if row is None:
                    return f"Memory '{target_id}' not found for user '{user}'."

                with conn:
                    if permanent:
                        conn.execute("DELETE FROM memories_vec WHERE memory_id = ?", (target_id,))
                        conn.execute("DELETE FROM memories_fts WHERE memory_id = ?", (target_id,))
                        conn.execute("DELETE FROM memories WHERE id = ?", (target_id,))
                        return f"Permanently deleted memory '{target_id}' for user '{user}'."
                    if row["deleted_at"]:
                        return f"Memory '{target_id}' is already in trash."
                    conn.execute(
                        "UPDATE memories SET deleted_at = ?, updated_at = ? WHERE id = ?",
                        (_now_iso(), _now_iso(), target_id),
                    )
                return f"Soft-deleted memory '{target_id}' (can be restored via `restore_memory`)."
            finally:
                conn.close()
    except Exception as e:
        return f"Error deleting memory: {str(e)}"


@mcp.tool()
async def restore_memory(memory_id: str, api_key: str = "") -> str:
    """
    Restore a soft-deleted memory from trash for the authenticated user.

    Args:
        memory_id: UUID of the soft-deleted memory to restore.
        api_key: Optional API key fallback if not passed via Authorization / X-API-Key header.
    """
    try:
        user = authenticate_user(api_key)
        target_id = (memory_id or "").strip()
        if not target_id:
            return "Error restoring memory: 'memory_id' cannot be empty."

        with _get_user_lock(user):
            conn = _open_user_db(user)
            try:
                row = conn.execute(
                    "SELECT id, deleted_at FROM memories WHERE id = ?", (target_id,)
                ).fetchone()
                if row is None:
                    return f"Memory '{target_id}' not found for user '{user}'."
                if not row["deleted_at"]:
                    return f"Memory '{target_id}' is not in trash."
                with conn:
                    conn.execute(
                        "UPDATE memories SET deleted_at = NULL, updated_at = ? WHERE id = ?",
                        (_now_iso(), target_id),
                    )
                return f"Restored memory '{target_id}' for user '{user}'."
            finally:
                conn.close()
    except Exception as e:
        return f"Error restoring memory: {str(e)}"


@mcp.tool()
async def purge_trash(namespace: str = "", api_key: str = "") -> str:
    """
    Permanently remove all soft-deleted memories for the authenticated user (optionally scoped
    to a single namespace).

    Args:
        namespace: Optional namespace filter; empty purges trash across all namespaces.
        api_key: Optional API key fallback if not passed via Authorization / X-API-Key header.
    """
    try:
        user = authenticate_user(api_key)
        ns_filter = _normalize_namespace(namespace) if (namespace or "").strip() else ""

        with _get_user_lock(user):
            conn = _open_user_db(user)
            try:
                if ns_filter:
                    rows = conn.execute(
                        "SELECT id FROM memories WHERE deleted_at IS NOT NULL AND namespace = ?",
                        (ns_filter,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT id FROM memories WHERE deleted_at IS NOT NULL"
                    ).fetchall()

                if not rows:
                    return f"Trash is already empty for user '{user}'."

                ids = [r["id"] for r in rows]
                placeholders = ",".join("?" for _ in ids)
                with conn:
                    conn.execute(f"DELETE FROM memories_vec WHERE memory_id IN ({placeholders})", ids)
                    conn.execute(f"DELETE FROM memories_fts WHERE memory_id IN ({placeholders})", ids)
                    conn.execute(f"DELETE FROM memories WHERE id IN ({placeholders})", ids)
                return f"Purged {len(ids)} trashed memory item(s) for user '{user}'."
            finally:
                conn.close()
    except Exception as e:
        return f"Error purging trash: {str(e)}"


@mcp.tool()
async def get_memory_stats(api_key: str = "") -> str:
    """
    Return storage statistics (active count, trashed count, namespaces, DB size, embedding config)
    for the authenticated user.

    Args:
        api_key: Optional API key fallback if not passed via Authorization / X-API-Key header.
    """
    try:
        user = authenticate_user(api_key)
        db_path = get_user_db_path(user)

        with _get_user_lock(user):
            conn = _open_user_db(user)
            try:
                with conn:
                    _prune_expired(conn)
                active_cnt = conn.execute(
                    "SELECT COUNT(*) FROM memories WHERE deleted_at IS NULL"
                ).fetchone()[0]
                trash_cnt = conn.execute(
                    "SELECT COUNT(*) FROM memories WHERE deleted_at IS NOT NULL"
                ).fetchone()[0]
                ns_rows = conn.execute(
                    "SELECT namespace, COUNT(*) AS cnt FROM memories WHERE deleted_at IS NULL GROUP BY namespace ORDER BY cnt DESC"
                ).fetchall()
            finally:
                conn.close()

        db_bytes = db_path.stat().st_size if db_path.exists() else 0
        ns_summary = ", ".join(f"{r['namespace']}={r['cnt']}" for r in ns_rows) or "none"
        return (
            f"Vector Memory Stats for '{user}':\n"
            f"- Active memories: {active_cnt}\n"
            f"- Trashed memories: {trash_cnt}\n"
            f"- Namespaces: {ns_summary}\n"
            f"- DB size: {db_bytes} bytes\n"
            f"- Embedding model: {EMBEDDING_MODEL} (dim={EMBEDDING_DIM})"
        )
    except Exception as e:
        return f"Error retrieving stats: {str(e)}"


@mcp.tool()
async def export_memories(
    namespace: str = "",
    format: str = "json",
    api_key: str = "",
) -> str:
    """
    Export active memories for the authenticated user as JSON or Markdown.

    Args:
        namespace: Optional namespace filter; empty exports all namespaces.
        format: Output format: "json" (default) or "markdown".
        api_key: Optional API key fallback if not passed via Authorization / X-API-Key header.
    """
    try:
        user = authenticate_user(api_key)
        ns_filter = _normalize_namespace(namespace) if (namespace or "").strip() else ""
        fmt = (format or "json").strip().lower()
        if fmt not in ("json", "markdown"):
            return "Error exporting memories: 'format' must be 'json' or 'markdown'."

        with _get_user_lock(user):
            conn = _open_user_db(user)
            try:
                with conn:
                    _prune_expired(conn)
                if ns_filter:
                    rows = conn.execute(
                        "SELECT * FROM memories WHERE deleted_at IS NULL AND namespace = ? ORDER BY created_at ASC",
                        (ns_filter,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM memories WHERE deleted_at IS NULL ORDER BY namespace ASC, created_at ASC"
                    ).fetchall()
            finally:
                conn.close()

        items = [
            {
                "id": r["id"],
                "namespace": r["namespace"],
                "doc_id": r["doc_id"],
                "chunk_index": r["chunk_index"],
                "content": r["content"],
                "tags": json.loads(r["tags"] or "[]"),
                "source": r["source"],
                "importance": r["importance"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "expires_at": r["expires_at"],
            }
            for r in rows
        ]

        if fmt == "json":
            return json.dumps({"user": user, "count": len(items), "memories": items}, indent=2)

        if not items:
            return f"# Vector Memory Export ({user})\n\nNo active memories."

        lines = [f"# Vector Memory Export ({user})", ""]
        for item in items:
            tag_str = ", ".join(item["tags"]) or "none"
            lines.append(
                f"- **[{item['namespace']}]** (imp={item['importance']}, tags={tag_str}, id=`{item['id']}`): {item['content']}"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Error exporting memories: {str(e)}"


if __name__ == "__main__":
    app = ApiKeyHeaderMiddleware(mcp.sse_app())
    uvicorn.run(app, host="0.0.0.0", port=8080)
