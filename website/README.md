# Website Scraper MCP (`website`)

HTML-to-Markdown scraping and link extraction MCP server (`Website-Scraper-Server`) exposing SSE on container port `8080` (host port `8084` via `docker-compose.yml`).

Includes SSRF protection (`validate_public_url` blocks non-`http(s)` schemes, `localhost`, `0.0.0.0`, loopback, link-local, and multicast addresses) and optional `robots.txt` checking (`AlpacaBot/1.0`).

## Tools

### `scrape_website(url: str, include_links: bool = True, include_images: bool = False, respect_robots: bool = True, max_length: int = 20000) -> str`
Fetch a public webpage, extract its title and meta description, strip `script`/`style`/`noscript`/`svg`/`iframe`/`canvas`/`form` tags, and convert HTML to clean Markdown. Non-HTML responses (e.g., `text/plain`, `application/json`) are returned directly.

- **Parameters**:
  - `url` (`str`, required): Public `http://` or `https://` URL.
  - `include_links` (`bool`, optional, default `True`): Preserve hyperlinks in Markdown output.
  - `include_images` (`bool`, optional, default `False`): Preserve image references in Markdown output.
  - `respect_robots` (`bool`, optional, default `True`): Check `robots.txt` before fetching.
  - `max_length` (`int`, optional, default `20000`): Maximum output character length, clamped to `[1000, 100000]`.

### `extract_website_links(url: str, same_domain_only: bool = False) -> str`
Fetch a public webpage and extract up to 100 unique `http`/`https` hyperlinks as a numbered Markdown list. Resolves relative links and skips `#`, `javascript:`, `mailto:`, and `tel:` links.

- **Parameters**:
  - `url` (`str`, required): Public `http://` or `https://` URL.
  - `same_domain_only` (`bool`, optional, default `False`): When `True`, return only links matching the source URL's hostname.

## How to Run

### Docker Compose (Recommended)
From the repository root:
```bash
docker compose up -d --build website
```
SSE endpoint: `http://localhost:8084/sse`

### Standalone Docker
```bash
docker build -t walpaca-mcp-website ./website
docker run -d --name walpaca_mcp_website -p 8084:8080 walpaca-mcp-website
```

### Local Python
```bash
cd website
pip install httpx beautifulsoup4 html2text "mcp<2"
python server.py
```
SSE endpoint: `http://localhost:8080/sse`

## Configure in Other Tools

### Generic MCP Client (SSE)
- **Transport**: `sse`
- **URL**: `http://localhost:8084/sse`

### JSON Client Config (Cursor / Windsurf / MCP-compatible clients)
```json
{
  "mcpServers": {
    "website": {
      "url": "http://localhost:8084/sse"
    }
  }
}
```

### Claude Desktop (via `mcp-remote` SSE bridge)
```json
{
  "mcpServers": {
    "website": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:8084/sse"]
    }
  }
}
```

## Usage Examples
- Convert documentation pages or blog articles into clean, token-efficient Markdown with `scrape_website(url, include_links=False)`.
- Discover subpages on a documentation site with `extract_website_links(url, same_domain_only=True)`, then scrape relevant pages.
- Read public API specs or text files while enforcing SSRF and `robots.txt` guards.
