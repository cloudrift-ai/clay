"""Bash command execution tool."""

import asyncio
import os
import subprocess
from typing import Optional, Dict, Any
from dataclasses import dataclass
import json
from .base import Tool, ToolResult, ToolStatus
from ..trace import trace_operation


@dataclass
class BashToolResult(ToolResult):
    """Specific result class for BashTool."""
    command: Optional[str] = None
    return_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    working_dir: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        base_dict = super().to_dict()
        base_dict.update({
            "command": self.command,
            "return_code": self.return_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "working_dir": self.working_dir
        })
        return base_dict

    def serialize_human_readable(self, max_lines: int = 10) -> str:
        """Serialize a human-readable version with bash-specific formatting."""
        result = {
            "status": self.status.value,
            "command": self.command,
            "return_code": self.return_code,
            "working_dir": self.working_dir
        }

        if self.error:
            result["error"] = self.error

        # Handle stdout with line limiting
        if self.stdout:
            lines = self.stdout.splitlines()
            if len(lines) <= max_lines:
                result["stdout"] = self.stdout
            else:
                truncated_output = '\n'.join(lines[:max_lines])
                result["stdout"] = truncated_output + f"\n... (truncated, showing {max_lines} of {len(lines)} lines)"

        # Handle stderr with line limiting
        if self.stderr:
            lines = self.stderr.splitlines()
            if len(lines) <= max_lines:
                result["stderr"] = self.stderr
            else:
                truncated_output = '\n'.join(lines[:max_lines])
                result["stderr"] = truncated_output + f"\n... (truncated, showing {max_lines} of {len(lines)} lines)"

        return json.dumps(result, indent=2)

    def get_summary(self) -> str:
        """Get a one-line summary of the command execution."""
        if self.status == ToolStatus.SUCCESS:
            lines_count = len(self.stdout.splitlines()) if self.stdout else 0
            if self.command and self.command.startswith('ls'):
                return f"Listed {lines_count} item(s)"
            elif self.command and (self.command.startswith('cat') or self.command.startswith('head')):
                return f"Displayed {lines_count} line(s)"
            elif self.command and self.command.startswith('grep'):
                return f"Found {lines_count} match(es)"
            elif self.command and self.command.startswith('find'):
                return f"Found {lines_count} file(s)"
            elif self.command and self.command.startswith('git diff'):
                lines = self.stdout.splitlines() if self.stdout else []
                added = sum(1 for line in lines if line.startswith('+') and not line.startswith('+++'))
                removed = sum(1 for line in lines if line.startswith('-') and not line.startswith('---'))
                return f"{added} addition(s), {removed} deletion(s)"
            elif self.command and self.command.startswith('git status'):
                lines = self.stdout.splitlines() if self.stdout else []
                modified = sum(1 for line in lines if 'modified:' in line)
                new = sum(1 for line in lines if 'new file:' in line)
                return f"{modified} modified, {new} new file(s)"
            elif lines_count > 0:
                return f"Command completed with {lines_count} line(s) of output"
            else:
                return "Command completed successfully"
        else:
            return f"Command failed with return code {self.return_code}"


class BashTool(Tool):
    """Execute bash commands."""

    def __init__(self, timeout: int = 120):
        super().__init__(
            name="bash",
            description="Execute shell commands and scripts for all development tasks including file operations, code management, and system tasks",
            capabilities=[
                "Create files: cat > file.py << 'EOF' ... EOF",
                "Read files: cat file.py, head file.py, tail file.py",
                "Edit files: sed, awk, or text editors like nano/vim",
                "List files: ls, find, locate",
                "Run commands: python, npm, git, make, etc.",
                "File operations: cp, mv, rm, chmod, mkdir",
                "Search text: grep, ripgrep (rg)",
                "Process management and system queries"
            ],
            use_cases=[
                "Create Python/JavaScript/any code files",
                "Read and analyze existing code files",
                "Edit configuration files and scripts",
                "Run build, test, and deployment commands",
                "Execute git operations and version control",
                "Install packages and manage dependencies",
                "Perform system administration tasks",
                "Search through codebases and logs"
            ]
        )
        self.default_timeout = timeout

    def get_example_usage(self) -> str:
        """Get example usage for the bash tool with multiple practical examples."""
        examples = [
            {
                "tool_name": "bash",
                "parameters": {
                    "command": "ls -la"
                },
                "description": "List all files in current directory with details"
            },
            {
                "tool_name": "bash",
                "parameters": {
                    "command": "cat > hello.py << 'EOF'\nprint('Hello, World!')\nEOF",
                    "working_dir": "/tmp"
                },
                "description": "Create a Python file in /tmp directory"
            },
            {
                "tool_name": "bash",
                "parameters": {
                    "command": "python -m pytest tests/",
                    "timeout": 300
                },
                "description": "Run tests with extended timeout"
            },
            {
                "tool_name": "bash",
                "parameters": {
                    "command": "find . -name '*.py' | head -10"
                },
                "description": "Find Python files and show first 10 results"
            }
        ]
        return json.dumps(examples, indent=2)

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute. Can be single commands like 'ls -la' or complex scripts with pipes, redirects, and multi-line heredocs",
                    "examples": [
                        "ls -la",
                        "python script.py",
                        "cat > file.txt << 'EOF'\ncontent here\nEOF",
                        "find . -name '*.py' | grep test | head -5",
                        "git status && git diff --name-only"
                    ]
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds for command execution (default: 120)",
                    "default": 120,
                    "minimum": 1,
                    "maximum": 3600,
                    "examples": [30, 120, 300]
                },
                "working_dir": {
                    "type": "string",
                    "description": "Working directory path where command should be executed (default: current directory)",
                    "examples": ["/tmp", "/home/user/project", ".", "../parent"]
                }
            },
            "required": ["command"],
            "additionalProperties": False
        }

    @trace_operation
    async def execute(
        self,
        command: str,
        timeout: Optional[int] = None,
        working_dir: Optional[str] = None
    ) -> BashToolResult:
        timeout = timeout or self.default_timeout
        working_dir = working_dir or os.getcwd()

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
                shell=True
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )

                stdout_str = stdout.decode('utf-8', errors='replace')
                stderr_str = stderr.decode('utf-8', errors='replace')

                result = BashToolResult(
                    status=ToolStatus.SUCCESS if process.returncode == 0 else ToolStatus.ERROR,
                    command=command,
                    return_code=process.returncode,
                    stdout=stdout_str,
                    stderr=stderr_str,
                    working_dir=working_dir,
                    output=stdout_str if stdout_str else stderr_str,
                    error=stderr_str if process.returncode != 0 else None,
                    metadata={"return_code": process.returncode}
                )

                # Add summary to metadata after result is created
                result.metadata["summary"] = result.get_summary()

                return result

            except asyncio.TimeoutError:
                process.terminate()
                await process.wait()
                return BashToolResult(
                    status=ToolStatus.ERROR,
                    command=command,
                    working_dir=working_dir,
                    error=f"Command timed out after {timeout} seconds"
                )

        except Exception as e:
            return BashToolResult(
                status=ToolStatus.ERROR,
                command=command,
                working_dir=working_dir,
                error=f"Failed to execute command: {str(e)}"
            )