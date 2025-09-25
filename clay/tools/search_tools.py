"""Search and grep tools."""

import re
import subprocess
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
from .base import Tool, ToolResult, ToolStatus


class GrepTool(Tool):
    """Search file contents using ripgrep."""

    def __init__(self):
        super().__init__(
            name="grep",
            description="Search through file contents using ripgrep with regex patterns, file type filters, and context display",
            capabilities=[
                "Search with regex patterns",
                "Filter by file types (py, js, etc.)",
                "Case-sensitive or insensitive search",
                "Show context lines around matches",
                "Fast recursive directory search",
                "Multiple output formats"
            ],
            use_cases=[
                "Find function definitions in code",
                "Search for specific error patterns",
                "Locate configuration settings",
                "Find usage of variables or classes",
                "Search documentation content",
                "Identify code patterns across files"
            ]
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Search pattern"},
                "path": {"type": "string", "description": "Path to search"},
                "file_type": {"type": "string", "description": "File type filter"},
                "case_sensitive": {"type": "boolean", "description": "Case sensitive search"},
                "context_lines": {"type": "integer", "description": "Context lines to show"}
            },
            "required": ["pattern"]
        }

    async def execute(
        self,
        pattern: str,
        path: str = ".",
        file_type: Optional[str] = None,
        case_sensitive: bool = True,
        context_lines: int = 0
    ) -> ToolResult:
        try:
            cmd = ["rg", pattern, path]

            if not case_sensitive:
                cmd.append("-i")

            if file_type:
                cmd.extend(["-t", file_type])

            if context_lines > 0:
                cmd.extend(["-C", str(context_lines)])

            cmd.append("--no-heading")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                output = stdout.decode('utf-8', errors='replace')
                return ToolResult(
                    status=ToolStatus.SUCCESS,
                    output=output
                )
            elif process.returncode == 1:
                return ToolResult(
                    status=ToolStatus.SUCCESS,
                    output="No matches found"
                )
            else:
                error = stderr.decode('utf-8', errors='replace')
                return ToolResult(
                    status=ToolStatus.ERROR,
                    error=f"Grep failed: {error}"
                )

        except FileNotFoundError:
            return await self._fallback_grep(pattern, path, case_sensitive)
        except Exception as e:
            return ToolResult(status=ToolStatus.ERROR, error=str(e))

    async def _fallback_grep(
        self,
        pattern: str,
        path: str,
        case_sensitive: bool
    ) -> ToolResult:
        """Fallback to Python-based grep if ripgrep not available."""
        try:
            search_path = Path(path).resolve()
            results = []
            flags = 0 if case_sensitive else re.IGNORECASE
            regex = re.compile(pattern, flags)

            if search_path.is_file():
                files = [search_path]
            else:
                files = search_path.rglob("*")

            for file_path in files:
                if file_path.is_file():
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            for line_num, line in enumerate(f, 1):
                                if regex.search(line):
                                    results.append(f"{file_path}:{line_num}:{line.rstrip()}")
                    except:
                        continue

            output = "\n".join(results) if results else "No matches found"
            return ToolResult(status=ToolStatus.SUCCESS, output=output)

        except Exception as e:
            return ToolResult(status=ToolStatus.ERROR, error=str(e))


class SearchTool(Tool):
    """High-level code search tool."""

    def __init__(self):
        super().__init__(
            name="search",
            description="High-level semantic code search that combines multiple search patterns and strategies for comprehensive results",
            capabilities=[
                "Extract multiple search patterns from queries",
                "Combine results from different search strategies",
                "Remove duplicate results",
                "Limit results to manageable size",
                "Semantic understanding of code queries",
                "Intelligent pattern extraction"
            ],
            use_cases=[
                "Find functions or classes by description",
                "Locate code implementing specific features",
                "Search for error handling patterns",
                "Find similar code structures",
                "Discover API usage examples",
                "Locate configuration or setup code"
            ]
        )
        self.grep_tool = GrepTool()

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "path": {"type": "string", "description": "Path to search"},
                "max_results": {"type": "integer", "description": "Maximum results"}
            },
            "required": ["query"]
        }

    async def execute(
        self,
        query: str,
        path: str = ".",
        max_results: int = 50
    ) -> ToolResult:
        patterns = self._extract_patterns(query)

        all_results = []
        for pattern in patterns:
            result = await self.grep_tool.execute(pattern, path=path)
            if result.status == ToolStatus.SUCCESS and result.output != "No matches found":
                all_results.extend(result.output.split("\n"))

        if not all_results:
            return ToolResult(
                status=ToolStatus.SUCCESS,
                output="No matches found"
            )

        unique_results = list(dict.fromkeys(all_results))[:max_results]
        return ToolResult(
            status=ToolStatus.SUCCESS,
            output="\n".join(unique_results),
            metadata={"total_matches": len(unique_results)}
        )

    def _extract_patterns(self, query: str) -> List[str]:
        """Extract search patterns from query."""
        words = query.split()

        patterns = []
        if len(words) == 1:
            patterns.append(words[0])
        else:
            patterns.append(" ".join(words))
            patterns.extend(words)

        return patterns