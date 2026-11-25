# Fetch MCP (`fetch`)

Raw HTTP GET retrieval MCP server (`Fetch-SSE-Server`) exposing SSE on container port `8080` (host port `8081` via `docker-compose.yml`).

## Tools

### `fetch_web_page(url: str) -> str`
Perform an HTTP GET request (following redirects) and return the raw response body as text.

- **Parameters**:
  - `url` (`str`, required): Full `http://` or `https://` URL to fetch (e.g., `https://example.com/api/data.json`).
- **Behavior**: Returns raw response body text (JSON, XML/RSS, plain text, or raw HTML) or an error message string if the request fails. For HTML-to-Markdown conversion, prefer `website` (`scrape_website`).

## How to Run

### Docker Compose (Recommended)
From the repository root:
```bash
docker compose up -d --build fetch
```
SSE endpoint: `http://localhost:8081/sse`

### Standalone Docker
```bash
docker build -t walpaca-mcp-fetch ./fetch
docker run -d --name walpaca_mcp_fetch -p 8081:8080 walpaca-mcp-fetch
```

### Local Python
```bash
cd fetch
pip install httpx "mcp<2"
python server.py
```
SSE endpoint: `http://localhost:8080/sse`

## Configure in Other Tools

### Generic MCP Client (SSE)
- **Transport**: `sse`
- **URL**: `http://localhost:8081/sse`

### JSON Client Config (Cursor / Windsurf / MCP-compatible clients)
```json
{
  "mcpServers": {
    "fetch": {
      "url": "http://localhost:8081/sse"
    }
  }
}
```

### Claude Desktop (via `mcp-remote` SSE bridge)
```json
{
  "mcpServers": {
    "fetch": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:8081/sse"]
    }
  }
}
```

## Usage Examples
- Fetch a public JSON API endpoint and inspect its payload.
- Download raw `robots.txt`, `sitemap.xml`, RSS/Atom feeds, or plain-text files.
- Retrieve raw HTML source when exact markup is needed instead of Markdown.
