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

    def console_summary(self) -> str:
        """Get a console-friendly summary of the file operation."""
        if self.status == ToolStatus.SUCCESS:
            if self.operation == "read":
                return f"✅ Read {self.file_path} ({self.lines_affected} lines)"
            elif self.operation == "write":
                return f"✅ Created {self.file_path} ({self.lines_affected} lines)"
            elif self.operation == "update":
                return f"✅ Updated {self.file_path} ({self.lines_affected} changes)"
            else:
                return f"✅ File operation completed on {self.file_path}"
        else:
            error_msg = self.error or "Unknown error"
            return f"❌ File operation failed: {error_msg}"


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
                output=f"Successfully wrote {lines_count} lines to {file_path}",
                file_path=file_path,
                lines_affected=lines_count,
                operation="write",
                metadata={
                    "encoding": encoding,
                    "file_size": file_size,
                    "created_dirs": create_dirs
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

        # Parse the unified diff to create a more readable format
        output_lines = []
        output_lines.append(f"⏺ Update({file_path})")

        # Count additions and deletions
        additions = sum(1 for line in diff_lines if line.startswith('+') and not line.startswith('+++'))
        deletions = sum(1 for line in diff_lines if line.startswith('-') and not line.startswith('---'))

        if additions > 0 and deletions > 0:
            output_lines.append(f"  ⎿  Updated {file_path} with {additions} additions and {deletions} deletions")
        elif additions > 0:
            output_lines.append(f"  ⎿  Updated {file_path} with {additions} additions")
        elif deletions > 0:
            output_lines.append(f"  ⎿  Updated {file_path} with {deletions} deletions")
        else:
            output_lines.append(f"  ⎿  Updated {file_path}")

        # Process the diff to show context with line numbers
        current_line = 0
        in_hunk = False

        for line in diff_lines:
            if line.startswith('@@'):
                # Parse hunk header to get line numbers
                parts = line.split(' ')
                if len(parts) >= 3:
                    old_range = parts[1][1:]  # Remove the '-'
                    new_range = parts[2][1:]  # Remove the '+'
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
                output_lines.append(f"       {current_line:3d}                {line[1:]}")
                current_line += 1
            elif line.startswith('-'):
                # Deleted line
                output_lines.append(f"       {current_line:3d} -              {line[1:]}")
                current_line += 1
            elif line.startswith('+'):
                # Added line
                output_lines.append(f"       {current_line:3d} +              {line[1:]}")
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