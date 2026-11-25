# Memory MCP (`memory`)

Folder-scoped JSON knowledge graph MCP server (`Memory-Server`) exposing SSE on container port `8080` (host port `8085` via `docker-compose.yml`).

Stores `(entity, relation, value)` facts under `MEMORY_DATA_DIR` (`/app/data` in Docker, `./memory/data` on host) in `<MEMORY_DATA_DIR>/folder_<uuid>/memory.json` with atomic writes, thread locking, and `trash.json` archiving on deletion. Folder scopes inherit global facts from `default` (read-only from non-default folders).

## Tools

### `store_fact(entity: str, relation: str, value: str, folder_uuid: str = "default") -> str`
Store or update a structured `(entity, relation, value)` fact in the isolated JSON knowledge graph for `folder_uuid`.

- **Parameters**:
  - `entity` (`str`, required): Subject or noun (normalized case-insensitively; display capitalization preserved).
  - `relation` (`str`, required): Attribute or relationship (normalized to `snake_case`).
  - `value` (`str`, required): Fact value to store.
  - `folder_uuid` (`str`, optional, default `"default"`): Workspace/folder scope matching `^[a-zA-Z0-9_-]{1,128}$` (leading `folder_` prefix is stripped).

### `recall_facts(query: str, folder_uuid: str = "default") -> str`
Search the scoped knowledge graph for facts matching `query`, merging `default` global facts with folder-specific overrides.

- **Parameters**:
  - `query` (`str`, required): Keyword, entity, topic, or `"all"` / `"*"` / `""` to list all facts in scope.
  - `folder_uuid` (`str`, optional, default `"default"`): Workspace/folder scope.
- **Behavior**: Ranks results via exact substring, token overlap, and `SequenceMatcher` similarity. Falls back to returning all scoped facts if no direct keyword hit is found.

### `delete_fact(entity: str, relation: str = "", folder_uuid: str = "default") -> str`
Remove a relation or an entire entity from `memory.json` and archive it to `trash.json` (or `trash_<timestamp>.json` on conflict).

- **Parameters**:
  - `entity` (`str`, required): Entity name to remove or curate.
  - `relation` (`str`, optional, default `""`): Specific relation key to delete; leave empty or pass `"*"` / `"all"` to delete the entire entity.
  - `folder_uuid` (`str`, optional, default `"default"`): Workspace/folder scope. Facts inherited from `default` cannot be deleted from another folder scope.

## Environment Variables
- `MEMORY_DATA_DIR`: Directory where `folder_<uuid>/memory.json` files are stored (default: `<repo>/memory/data`, `/app/data` in Docker).

## How to Run

### Docker Compose (Recommended)
From the repository root:
```bash
docker compose up -d --build memory
```
SSE endpoint: `http://localhost:8085/sse`

### Standalone Docker
```bash
docker build -t walpaca-mcp-memory ./memory
docker run -d --name walpaca_mcp_memory -p 8085:8080 -v "$(pwd)/memory/data:/app/data" walpaca-mcp-memory
```

### Local Python
```bash
cd memory
pip install "mcp<2"
MEMORY_DATA_DIR=./data python server.py
```
SSE endpoint: `http://localhost:8080/sse`

## Configure in Other Tools

### Generic MCP Client (SSE)
- **Transport**: `sse`
- **URL**: `http://localhost:8085/sse`

### JSON Client Config (Cursor / Windsurf / MCP-compatible clients)
```json
{
  "mcpServers": {
    "memory": {
      "url": "http://localhost:8085/sse"
    }
  }
}
```

### Claude Desktop (via `mcp-remote` SSE bridge)
```json
{
  "mcpServers": {
    "memory": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:8085/sse"]
    }
  }
}
```

## Usage Examples
- Persist user preferences (`store_fact("User", "preferred_editor", "Neovim")`) across sessions.
- Isolate project-specific facts per workspace using `folder_uuid` while inheriting global user facts from `default`.
- Curate or forget outdated specs with `delete_fact` while retaining an audit trail in `trash.json`.
