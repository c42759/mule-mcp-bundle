# Web Search MCP (`web-search`)

DuckDuckGo web search and raw HTTP GET MCP server (`DuckDuckGo-Search-Server`) exposing SSE on container port `8080` (host port `8082` via `docker-compose.yml`).

## Tools

### `search_ddg(query: str, max_results: int = 5) -> str`
Search the web using DuckDuckGo (`ddgs`) and return a numbered list of matching pages.

- **Parameters**:
  - `query` (`str`, required): Search keywords or natural-language query.
  - `max_results` (`int`, optional, default `5`): Maximum number of results to return.
- **Behavior**: Returns numbered results with `Title`, `URL`, and `Snippet`, or a no-results/error message.

### `fetch_web_page(url: str) -> str`
Perform an HTTP GET request (following redirects) and return the raw response body as text.

- **Parameters**:
  - `url` (`str`, required): Full `http://` or `https://` URL to fetch.
- **Behavior**: Returns raw response body text (raw HTML without Markdown conversion, JSON, or plain text).

## How to Run

### Docker Compose (Recommended)
From the repository root:
```bash
docker compose up -d --build web-search
```
SSE endpoint: `http://localhost:8082/sse`

### Standalone Docker
```bash
docker build -t walpaca-mcp-web-search ./web-search
docker run -d --name walpaca_mcp_web_search -p 8082:8080 walpaca-mcp-web-search
```

### Local Python
```bash
cd web-search
pip install httpx ddgs "mcp<2"
python server.py
```
SSE endpoint: `http://localhost:8080/sse`

## Configure in Other Tools

### Generic MCP Client (SSE)
- **Transport**: `sse`
- **URL**: `http://localhost:8082/sse`

### JSON Client Config (Cursor / Windsurf / MCP-compatible clients)
```json
{
  "mcpServers": {
    "web-search": {
      "url": "http://localhost:8082/sse"
    }
  }
}
```

### Claude Desktop (via `mcp-remote` SSE bridge)
```json
{
  "mcpServers": {
    "web-search": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:8082/sse"]
    }
  }
}
```

## Usage Examples
- Look up up-to-date documentation, release notes, or error messages.
- Discover relevant URLs with `search_ddg`, then retrieve raw content via `fetch_web_page` or `website` (`scrape_website`).
- Verify current facts or compare software libraries without knowing exact URLs upfront.
