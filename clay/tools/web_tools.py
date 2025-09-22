"""Web-based tools for fetching and searching."""

import aiohttp
import asyncio
from typing import Optional, Dict, Any, List
from .base import Tool, ToolResult, ToolStatus


class WebFetchTool(Tool):
    """Fetch content from URLs."""

    def __init__(self):
        super().__init__(
            name="web_fetch",
            description="Fetch content from a URL"
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"},
                "timeout": {"type": "integer", "description": "Request timeout"}
            },
            "required": ["url"]
        }

    async def execute(self, url: str, timeout: int = 30) -> ToolResult:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=timeout) as response:
                    if response.status == 200:
                        content = await response.text()
                        return ToolResult(
                            status=ToolStatus.SUCCESS,
                            output=content,
                            metadata={"status_code": response.status, "url": url}
                        )
                    else:
                        return ToolResult(
                            status=ToolStatus.ERROR,
                            error=f"HTTP {response.status}: {response.reason}"
                        )
        except asyncio.TimeoutError:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Request timed out after {timeout} seconds"
            )
        except Exception as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Failed to fetch URL: {str(e)}"
            )


class WebSearchTool(Tool):
    """Search the web for information."""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            name="web_search",
            description="Search the web"
        )
        self.api_key = api_key

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Maximum results"}
            },
            "required": ["query"]
        }

    async def execute(self, query: str, max_results: int = 10) -> ToolResult:
        if not self.api_key:
            return ToolResult(
                status=ToolStatus.ERROR,
                error="Web search requires API key configuration"
            )

        try:
            results = await self._search(query, max_results)

            formatted_results = []
            for i, result in enumerate(results, 1):
                formatted_results.append(
                    f"{i}. {result['title']}\n   {result['url']}\n   {result['snippet']}"
                )

            return ToolResult(
                status=ToolStatus.SUCCESS,
                output="\n\n".join(formatted_results),
                metadata={"count": len(results), "query": query}
            )
        except Exception as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Search failed: {str(e)}"
            )

    async def _search(self, query: str, max_results: int) -> List[Dict[str, str]]:
        """Placeholder for actual search implementation."""
        return [
            {
                "title": f"Result for: {query}",
                "url": f"https://example.com/search?q={query}",
                "snippet": "This would be actual search results when API is configured."
            }
        ]