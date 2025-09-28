"""File manipulation tools for reading, writing, and updating files."""

import os
import difflib
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from pathlib import Path

from .base import Tool, ToolResult, ToolStatus
from ..trace import trace_operation


@dataclass
class FileToolResult(ToolResult):
    """Specific result class for file tools."""
    file_path: Optional[str] = None
    lines_affected: Optional[int] = None
    operation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        base_dict = super().to_dict()
        base_dict.update({
            "file_path": self.file_path,
            "lines_affected": self.lines_affected,
            "operation": self.operation
        })
        return base_dict

    def get_formatted_output(self) -> str:
        """Get formatted output for Claude Code style display."""
        if self.status == ToolStatus.SUCCESS:
            if self.operation == "read":
                # For read operations, show the content (it's already formatted with line numbers)
                return self.output or f"Read {self.lines_affected} lines from {self.file_path}"
            elif self.operation == "write":
                # For write operations, show the actual content
                if self.output:
                    # Format the content with line numbers for display
                    lines = self.output.splitlines()
                    formatted_lines = []
                    for i, line in enumerate(lines, 1):
                        formatted_lines.append(f"{i:4d}→ {line}")
                    return '\n'.join(formatted_lines)
                else:
                    return f"Created {self.file_path} with {self.lines_affected} lines"
            elif self.operation == "update":
                # For update operations, show the diff output
                if self.output and "⏺ Update" not in self.output:
                    # Return the diff output without the header
                    return self.output
                elif self.output:
                    # Extract just the diff part
                    lines = self.output.splitlines()
                    if len(lines) > 2:
                        return '\n'.join(lines[1:])  # Skip the ⏺ Update line
                return f"Updated {self.file_path} with {self.lines_affected} changes"
            else:
                return self.output or "File operation completed"
        else:
            return f"Error: {self.error or 'File operation failed'}"


class ReadTool(Tool):
    """Read file contents."""

    def __init__(self):
        super().__init__(
            name="read",
            description="Read the contents of a file",
            capabilities=[
                "Read entire file contents",
                "Read specific line ranges",
                "Handle various text encodings",
                "Show file metadata"
            ],
            use_cases=[
                "Examine existing code files",
                "Read configuration files",
                "Inspect log files",
                "Analyze file content before modifications"
            ]
        )

    def get_tool_call_display(self, parameters: Dict[str, Any]) -> str:
        """Get formatted display for read tool invocation."""
        file_path = parameters.get('file_path', '')
        if len(file_path) > 60:
            file_path = "..." + file_path[-57:]
        return f"⏺ Read({file_path})"

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to read"
                },
                "start_line": {
                    "type": "integer",
                    "description": "Starting line number (1-indexed, optional)",
                    "minimum": 1
                },
                "end_line": {
                    "type": "integer",
                    "description": "Ending line number (1-indexed, optional)",
                    "minimum": 1
                },
                "encoding": {
                    "type": "string",
                    "description": "File encoding (default: utf-8)",
                    "default": "utf-8"
                }
            },
            "required": ["file_path"]
        }

    @trace_operation
    async def execute(
        self,
        file_path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        encoding: str = "utf-8"
    ) -> FileToolResult:
        try:
            if not os.path.exists(file_path):
                return FileToolResult(
                    status=ToolStatus.ERROR,
                    error=f"File not found: {file_path}",
                    file_path=file_path,
                    operation="read"
                )

            with open(file_path, 'r', encoding=encoding) as f:
                lines = f.readlines()

            # Apply line range if specified
            if start_line is not None or end_line is not None:
                start_idx = (start_line - 1) if start_line else 0
                end_idx = end_line if end_line else len(lines)
                lines = lines[start_idx:end_idx]

            content = ''.join(lines)
            lines_count = len(lines)

            # Format output with line numbers
            output_lines = []
            base_line_num = start_line if start_line else 1
            for i, line in enumerate(lines):
                line_num = base_line_num + i
                output_lines.append(f"{line_num:4d}→ {line.rstrip()}")

            formatted_output = '\n'.join(output_lines)

            return FileToolResult(
                status=ToolStatus.SUCCESS,
                output=formatted_output,
                file_path=file_path,
                lines_affected=lines_count,
                operation="read",
                metadata={
                    "encoding": encoding,
                    "total_lines": lines_count,
                    "file_size": os.path.getsize(file_path)
                }
            )

        except UnicodeDecodeError as e:
            return FileToolResult(
                status=ToolStatus.ERROR,
                error=f"Encoding error reading {file_path}: {str(e)}",
                file_path=file_path,
                operation="read"
            )
        except Exception as e:
            return FileToolResult(
                status=ToolStatus.ERROR,
                error=f"Failed to read {file_path}: {str(e)}",
                file_path=file_path,
                operation="read"
            )


class WriteTool(Tool):
    """Write content to a file."""

    def __init__(self):
        super().__init__(
            name="write",
            description="Write content to a file, creating or overwriting it",
            capabilities=[
                "Create new files",
                "Overwrite existing files",
                "Handle various text encodings",
                "Create parent directories if needed"
            ],
            use_cases=[
                "Create new source code files",
                "Generate configuration files",
                "Write documentation",
                "Create test files"
            ]
        )

    def get_tool_call_display(self, parameters: Dict[str, Any]) -> str:
        """Get formatted display for write tool invocation."""
        file_path = parameters.get('file_path', '')
        if len(file_path) > 60:
            file_path = "..." + file_path[-57:]
        return f"⏺ Write({file_path})"

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path where to write the file"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                },
                "encoding": {
                    "type": "string",
                    "description": "File encoding (default: utf-8)",
                    "default": "utf-8"
                },
                "create_dirs": {
                    "type": "boolean",
                    "description": "Create parent directories if they don't exist (default: true)",
                    "default": True
                }
            },
            "required": ["file_path", "content"]
        }

    @trace_operation
    async def execute(
        self,
        file_path: str,
        content: str,
        encoding: str = "utf-8",
        create_dirs: bool = True
    ) -> FileToolResult:
        try:
            file_path_obj = Path(file_path)

            # Create parent directories if needed
            if create_dirs and file_path_obj.parent != Path('.'):
                file_path_obj.parent.mkdir(parents=True, exist_ok=True)

            # Write the file
            with open(file_path, 'w', encoding=encoding) as f:
                f.write(content)

            lines_count = len(content.splitlines())
            file_size = os.path.getsize(file_path)

            return FileToolResult(
                status=ToolStatus.SUCCESS,
                output=content,  # Store the actual content
                file_path=file_path,
                lines_affected=lines_count,
                operation="write",
                metadata={
                    "encoding": encoding,
                    "file_size": file_size,
                    "created_dirs": create_dirs,
                    "content": content  # Also store in metadata for reference
                }
            )

        except Exception as e:
            return FileToolResult(
                status=ToolStatus.ERROR,
                error=f"Failed to write {file_path}: {str(e)}",
                file_path=file_path,
                operation="write"
            )


class UpdateTool(Tool):
    """Update a file by replacing specific content with new content."""

    def __init__(self):
        super().__init__(
            name="update",
            description="Update a file by replacing old content with new content, showing detailed diff",
            capabilities=[
                "Replace exact text matches",
                "Show detailed diff output",
                "Preserve file formatting",
                "Handle multiple occurrences"
            ],
            use_cases=[
                "Modify existing code files",
                "Update configuration values",
                "Patch documentation",
                "Refactor code sections"
            ]
        )

    def get_tool_call_display(self, parameters: Dict[str, Any]) -> str:
        """Get formatted display for update tool invocation."""
        file_path = parameters.get('file_path', '')
        if len(file_path) > 60:
            file_path = "..." + file_path[-57:]
        return f"⏺ Update({file_path})"

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to update"
                },
                "old_content": {
                    "type": "string",
                    "description": "Exact content to replace (must match exactly including whitespace)"
                },
                "new_content": {
                    "type": "string",
                    "description": "New content to replace the old content with"
                },
                "encoding": {
                    "type": "string",
                    "description": "File encoding (default: utf-8)",
                    "default": "utf-8"
                },
                "replace_all": {
                    "type": "boolean",
                    "description": "Replace all occurrences (default: false - replace first match only)",
                    "default": False
                }
            },
            "required": ["file_path", "old_content", "new_content"]
        }

    def _generate_diff_output(self, file_path: str, old_lines: List[str], new_lines: List[str]) -> str:
        """Generate patch-style diff output."""
        # Find the differences
        differ = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm=""
        )

        diff_lines = list(differ)
        if len(diff_lines) <= 2:  # Only header lines, no actual changes
            return "No changes detected"

        # Count additions and deletions
        additions = sum(1 for line in diff_lines if line.startswith('+') and not line.startswith('+++'))
        deletions = sum(1 for line in diff_lines if line.startswith('-') and not line.startswith('---'))

        # Build summary line
        if additions > 0 and deletions > 0:
            summary = f"Updated {file_path} with {additions} additions and {deletions} deletions"
        elif additions > 0:
            summary = f"Updated {file_path} with {additions} additions"
        elif deletions > 0:
            summary = f"Updated {file_path} with {deletions} deletions"
        else:
            summary = f"Updated {file_path}"

        output_lines = [summary]

        # Process the diff to show context with line numbers
        current_line = 0
        in_hunk = False

        for line in diff_lines:
            if line.startswith('@@'):
                # Parse hunk header to get line numbers
                parts = line.split(' ')
                if len(parts) >= 3:
                    old_range = parts[1][1:]  # Remove the '-'
                    if ',' in old_range:
                        old_start = int(old_range.split(',')[0])
                    else:
                        old_start = int(old_range)
                    current_line = old_start
                in_hunk = True
                continue

            if not in_hunk:
                continue

            if line.startswith(' '):
                # Context line
                output_lines.append(f"  {current_line:3d}                {line[1:]}")
                current_line += 1
            elif line.startswith('-'):
                # Deleted line
                output_lines.append(f"  {current_line:3d} -              {line[1:]}")
                current_line += 1
            elif line.startswith('+'):
                # Added line - use new line number
                output_lines.append(f"  {current_line:3d} +              {line[1:]}")
                # Don't increment current_line for additions

        return '\n'.join(output_lines)

    @trace_operation
    async def execute(
        self,
        file_path: str,
        old_content: str,
        new_content: str,
        encoding: str = "utf-8",
        replace_all: bool = False
    ) -> FileToolResult:
        try:
            if not os.path.exists(file_path):
                return FileToolResult(
                    status=ToolStatus.ERROR,
                    error=f"File not found: {file_path}",
                    file_path=file_path,
                    operation="update"
                )

            # Read the current file content
            with open(file_path, 'r', encoding=encoding) as f:
                original_content = f.read()

            # Store original lines for diff
            original_lines = original_content.splitlines(keepends=True)

            # Perform the replacement
            if replace_all:
                updated_content = original_content.replace(old_content, new_content)
                replacements = original_content.count(old_content)
            else:
                updated_content = original_content.replace(old_content, new_content, 1)
                replacements = 1 if old_content in original_content else 0

            if replacements == 0:
                return FileToolResult(
                    status=ToolStatus.ERROR,
                    error=f"Old content not found in {file_path}",
                    file_path=file_path,
                    operation="update"
                )

            # Write the updated content
            with open(file_path, 'w', encoding=encoding) as f:
                f.write(updated_content)

            # Generate diff output
            updated_lines = updated_content.splitlines(keepends=True)
            diff_output = self._generate_diff_output(file_path, original_lines, updated_lines)

            return FileToolResult(
                status=ToolStatus.SUCCESS,
                output=diff_output,
                file_path=file_path,
                lines_affected=replacements,
                operation="update",
                metadata={
                    "replacements": replacements,
                    "encoding": encoding,
                    "replace_all": replace_all
                }
            )

        except Exception as e:
            return FileToolResult(
                status=ToolStatus.ERROR,
                error=f"Failed to update {file_path}: {str(e)}",
                file_path=file_path,
                operation="update"
            )