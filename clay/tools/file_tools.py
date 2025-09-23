"""File operation tools."""

import os
import glob
import aiofiles
from pathlib import Path
from typing import Optional, List, Dict, Any
from .base import Tool, ToolResult, ToolStatus, ToolError


class ReadTool(Tool):
    """Read files from the filesystem."""

    def __init__(self):
        super().__init__(
            name="read",
            description="Read a file from the filesystem"
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to file to read"},
                "offset": {"type": "integer", "description": "Line offset to start reading"},
                "limit": {"type": "integer", "description": "Maximum lines to read"}
            },
            "required": ["file_path"]
        }

    async def execute(self, file_path: str, offset: int = 0, limit: int = 2000) -> ToolResult:
        try:
            path = Path(file_path).resolve()
            if not path.exists():
                return ToolResult(
                    status=ToolStatus.ERROR,
                    error=f"File not found: {file_path}"
                )

            async with aiofiles.open(path, 'r', encoding='utf-8') as f:
                lines = await f.readlines()

            selected_lines = lines[offset:offset + limit] if limit else lines[offset:]

            output = []
            for i, line in enumerate(selected_lines, start=offset + 1):
                output.append(f"{i:6d}\t{line.rstrip()}")

            # Print summary to console
            from rich.console import Console
            console = Console()
            console.print(f"  [dim]→ Read {len(selected_lines)} lines from {file_path}[/dim]")

            return ToolResult(
                status=ToolStatus.SUCCESS,
                output="\n".join(output),
                metadata={"total_lines": len(lines), "lines_read": len(selected_lines)}
            )
        except Exception as e:
            return ToolResult(status=ToolStatus.ERROR, error=str(e))


class WriteTool(Tool):
    """Write files to the filesystem."""

    def __init__(self):
        super().__init__(
            name="write",
            description="Write a file to the filesystem"
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to write file"},
                "content": {"type": "string", "description": "Content to write"}
            },
            "required": ["file_path", "content"]
        }

    async def execute(self, file_path: str, content: str) -> ToolResult:
        try:
            path = Path(file_path).resolve()
            path.parent.mkdir(parents=True, exist_ok=True)

            # Check if file exists for showing if it's new or overwritten
            is_new = not path.exists()

            async with aiofiles.open(path, 'w', encoding='utf-8') as f:
                await f.write(content)

            # Print summary to console
            from rich.console import Console
            console = Console()
            line_count = len(content.splitlines())
            action = "Created new" if is_new else "Overwrote"
            console.print(f"  [dim]→ {action} file with {line_count} lines[/dim]")

            return ToolResult(
                status=ToolStatus.SUCCESS,
                output=f"File written: {file_path}"
            )
        except Exception as e:
            return ToolResult(status=ToolStatus.ERROR, error=str(e))


class EditTool(Tool):
    """Edit files with find-replace operations."""

    def __init__(self):
        super().__init__(
            name="edit",
            description="Edit a file with find-replace"
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to file to edit"},
                "old_string": {"type": "string", "description": "String to find"},
                "new_string": {"type": "string", "description": "String to replace with"},
                "replace_all": {"type": "boolean", "description": "Replace all occurrences"}
            },
            "required": ["file_path", "old_string", "new_string"]
        }

    async def execute(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False
    ) -> ToolResult:
        try:
            path = Path(file_path).resolve()
            if not path.exists():
                return ToolResult(
                    status=ToolStatus.ERROR,
                    error=f"File not found: {file_path}"
                )

            async with aiofiles.open(path, 'r', encoding='utf-8') as f:
                content = await f.read()

            if old_string not in content:
                return ToolResult(
                    status=ToolStatus.ERROR,
                    error=f"String not found in file: {old_string}"
                )

            if replace_all:
                new_content = content.replace(old_string, new_string)
                count = content.count(old_string)
            else:
                new_content = content.replace(old_string, new_string, 1)
                count = 1

            async with aiofiles.open(path, 'w', encoding='utf-8') as f:
                await f.write(new_content)

            # Print summary with diff preview
            from rich.console import Console
            from rich.syntax import Syntax
            console = Console()

            # Show a snippet of the change
            console.print(f"  [dim]→ Replaced {count} occurrence(s)[/dim]")

            # Show a small diff preview if changes are small enough
            if len(old_string) < 200 and len(new_string) < 200:
                console.print("  [red]- " + old_string[:100] + ("..." if len(old_string) > 100 else "") + "[/red]")
                console.print("  [green]+ " + new_string[:100] + ("..." if len(new_string) > 100 else "") + "[/green]")

            return ToolResult(
                status=ToolStatus.SUCCESS,
                output=f"Replaced {count} occurrence(s) in {file_path}"
            )
        except Exception as e:
            return ToolResult(status=ToolStatus.ERROR, error=str(e))


class GlobTool(Tool):
    """Find files matching patterns."""

    def __init__(self):
        super().__init__(
            name="glob",
            description="Find files matching glob patterns"
        )

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern to match"},
                "path": {"type": "string", "description": "Base path to search"}
            },
            "required": ["pattern"]
        }

    async def execute(self, pattern: str, path: str = ".") -> ToolResult:
        try:
            base_path = Path(path).resolve()
            full_pattern = str(base_path / pattern)

            matches = glob.glob(full_pattern, recursive=True)
            matches.sort(key=lambda p: os.path.getmtime(p), reverse=True)

            # Print summary to console
            from rich.console import Console
            console = Console()
            if matches:
                console.print(f"  [dim]→ Found {len(matches)} file(s) matching pattern[/dim]")
                # Show first few matches as preview
                if len(matches) <= 3:
                    for match in matches:
                        console.print(f"    [dim]• {Path(match).name}[/dim]")
                else:
                    for match in matches[:2]:
                        console.print(f"    [dim]• {Path(match).name}[/dim]")
                    console.print(f"    [dim]• ... and {len(matches) - 2} more[/dim]")
            else:
                console.print(f"  [dim]→ No files found matching pattern[/dim]")

            return ToolResult(
                status=ToolStatus.SUCCESS,
                output="\n".join(matches) if matches else "No matches found",
                metadata={"count": len(matches)}
            )
        except Exception as e:
            return ToolResult(status=ToolStatus.ERROR, error=str(e))