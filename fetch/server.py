import httpx

from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("Fetch-SSE-Server", host="0.0.0.0", port=8080)

@mcp.tool()
async def fetch_web_page(url: str) -> str:
    """
    Perform an HTTP GET request to a URL (following redirects) and return the raw response body as text.

    Use this when you need raw, unprocessed content such as JSON APIs, plain-text files, XML/RSS feeds,
    or raw HTML source. For human-readable webpages where you want scripts/styles stripped and HTML
    converted to clean Markdown, prefer `scrape_website` if available.

    Args:
        url: Full http:// or https:// URL to fetch (e.g., "https://example.com/api/data.json").

    Returns:
        Raw response body text, or an error message if the request fails.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, follow_redirects=True)
            return response.text
        except Exception as e:
            return f"Error fetching URL: {str(e)}"

if __name__ == "__main__":
    # FastMCP handles uvicorn and the SSE transport out of the box
    mcp.run(transport="sse")
