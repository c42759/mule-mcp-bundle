# YouTube Transcript MCP (`youtube`)

YouTube caption and subtitle retrieval MCP server (`YouTube-Transcript-Server`) exposing SSE on container port `8080` (host port `8083` via `docker-compose.yml`).

Supports standard `/watch?v=...` URLs, `youtu.be` short links, `/shorts/`, `/embed/`, `/v/`, `/live/` URLs, and raw 11-character video IDs. Fetches video title/channel metadata via `noembed.com` and transcripts via `youtube-transcript-api`.

## Tools

### `get_youtube_transcript(url_or_id: str, languages: str = "en", include_timestamps: bool = False) -> str`
Fetch video metadata (`Title`, `Channel`, `URL`, `Language`) and the full caption/subtitle transcript.

- **Parameters**:
  - `url_or_id` (`str`, required): YouTube URL or 11-character video ID.
  - `languages` (`str`, optional, default `"en"`): Comma-separated preferred ISO language codes in priority order (e.g., `"en,es,pt"`). Falls back to any available transcript if preferred languages are absent.
  - `include_timestamps` (`bool`, optional, default `False`): Prefix each line with `[MM:SS]` or `[HH:MM:SS]` when `True`.

### `query_youtube_transcript(url_or_id: str, query: str, languages: str = "en", context_window: int = 2) -> str`
Search a video's transcript for a case-insensitive keyword or phrase and return up to 25 matching timestamped excerpts with surrounding context segments.

- **Parameters**:
  - `url_or_id` (`str`, required): YouTube URL or 11-character video ID.
  - `query` (`str`, required): Keyword or phrase to search. If empty, returns the full timestamped transcript.
  - `languages` (`str`, optional, default `"en"`): Comma-separated preferred ISO language codes.
  - `context_window` (`int`, optional, default `2`): Number of segments before and after each match, clamped to `[0, 10]`.
- **Behavior**: If no exact substring match is found, returns a preview of the first 40 transcript segments.

## How to Run

### Docker Compose (Recommended)
From the repository root:
```bash
docker compose up -d --build youtube
```
SSE endpoint: `http://localhost:8083/sse`

### Standalone Docker
```bash
docker build -t walpaca-mcp-youtube ./youtube
docker run -d --name walpaca_mcp_youtube -p 8083:8080 walpaca-mcp-youtube
```

### Local Python
```bash
cd youtube
pip install httpx youtube-transcript-api "mcp<2"
python server.py
```
SSE endpoint: `http://localhost:8080/sse`

## Configure in Other Tools

### Generic MCP Client (SSE)
- **Transport**: `sse`
- **URL**: `http://localhost:8083/sse`

### JSON Client Config (Cursor / Windsurf / MCP-compatible clients)
```json
{
  "mcpServers": {
    "youtube": {
      "url": "http://localhost:8083/sse"
    }
  }
}
```

### Claude Desktop (via `mcp-remote` SSE bridge)
```json
{
  "mcpServers": {
    "youtube": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:8083/sse"]
    }
  }
}
```

## Usage Examples
- Summarize a conference talk, lecture, or tutorial video using `get_youtube_transcript`.
- Jump to exact timestamps where a topic is discussed in a long podcast using `query_youtube_transcript`.
- Extract quotes or code explanations with `include_timestamps=True`.
