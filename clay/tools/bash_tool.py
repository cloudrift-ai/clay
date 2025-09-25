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
            description="Execute shell commands and scripts with configurable timeout and working directory support",
            capabilities=[
                "Run any shell command or script",
                "Capture stdout and stderr output",
                "Set custom working directories",
                "Configure execution timeouts",
                "Handle command failures gracefully",
                "Support complex shell operations (pipes, redirects, etc.)"
            ],
            use_cases=[
                "Run build and compilation commands",
                "Execute test suites and scripts",
                "Install packages and dependencies",
                "Run git commands and version control",
                "Execute system administration tasks",
                "Launch applications and services",
                "Perform file operations and system queries"
            ]
        )
        self.default_timeout = timeout

    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command to execute"},
                "timeout": {"type": "integer", "description": "Timeout in seconds"},
                "working_dir": {"type": "string", "description": "Working directory"}
            },
            "required": ["command"]
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

                # Print summary to console
                from rich.console import Console
                console = Console()

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

                # Print summary using the result's get_summary method
                console.print(f"  [dim]→ {result.get_summary()}[/dim]")

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