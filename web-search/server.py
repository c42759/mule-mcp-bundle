import httpx

from ddgs import DDGS  # Clean import from the new package name
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("DuckDuckGo-Search-Server", host="0.0.0.0", port=8080)

@mcp.tool()
async def search_ddg(query: str, max_results: int = 5) -> str:
    """
    Search the web using DuckDuckGo and return a numbered list of matching pages.

    Use this when you need up-to-date information, want to discover relevant websites, verify facts,
    or find documentation without having a specific URL yet. Follow up with `fetch_web_page` or
    `scrape_website` on promising result URLs to read full page content.

    Args:
        query: Search keywords or natural-language query (e.g., "python asyncio gather example").
        max_results: Maximum number of search results to return (default 5).

    Returns:
        Numbered list of results with Title, URL, and Snippet, or a message if no results were found.
    """
    try:
        # Using the context manager from the updated ddgs package
        with DDGS() as ddgs:
            # FIX: Changed 'keywords=' to 'query='
            results = list(ddgs.text(query=query, max_results=max_results))
            
        if not results:
            return f"No results found for query: '{query}'"
            
        # Format the results into an LLM-friendly text block
        formatted_results = []
        for i, res in enumerate(results, start=1):
            formatted_results.append(
                f"{i}. Title: {res.get('title')}\n"
                f"   URL: {res.get('href')}\n"
                f"   Snippet: {res.get('body')}\n"
            )
        return "\n".join(formatted_results)

    except Exception as e:
        return f"Error executing DuckDuckGo search: {str(e)}"

@mcp.tool()
async def fetch_web_page(url: str) -> str:
    """
    Perform an HTTP GET request to a URL (following redirects) and return the raw response body as text.

    Use this to retrieve the raw content of a specific URL (such as a URL returned by `search_ddg`,
    a JSON endpoint, or a plain-text file). Note that HTML pages are returned as raw HTML without
    Markdown conversion.

    Args:
        url: Full http:// or https:// URL to fetch (e.g., "https://example.com/docs/overview").

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
