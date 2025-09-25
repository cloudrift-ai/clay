"""Bash command execution tool."""

import asyncio
import os
import subprocess
from typing import Optional, Dict, Any
from .base import Tool, ToolResult, ToolStatus
from ..trace import trace_operation


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
    ) -> ToolResult:
        timeout = timeout or self.default_timeout

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir or os.getcwd(),
                shell=True
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )

                output = stdout.decode('utf-8', errors='replace')
                error = stderr.decode('utf-8', errors='replace')

                # Print summary to console
                from rich.console import Console
                console = Console()

                if process.returncode == 0:
                    # Summarize command output
                    lines = output.splitlines() if output else []
                    if command.startswith('ls'):
                        file_count = len(lines)
                        console.print(f"  [dim]→ Listed {file_count} item(s)[/dim]")
                    elif command.startswith('cat') or command.startswith('head'):
                        console.print(f"  [dim]→ Displayed {len(lines)} line(s)[/dim]")
                    elif command.startswith('grep'):
                        console.print(f"  [dim]→ Found {len(lines)} match(es)[/dim]")
                    elif command.startswith('find'):
                        console.print(f"  [dim]→ Found {len(lines)} file(s)[/dim]")
                    elif command.startswith('git diff'):
                        # Count added/removed lines
                        added = sum(1 for line in lines if line.startswith('+') and not line.startswith('+++'))
                        removed = sum(1 for line in lines if line.startswith('-') and not line.startswith('---'))
                        console.print(f"  [dim]→ {added} addition(s), {removed} deletion(s)[/dim]")
                    elif command.startswith('git status'):
                        modified = sum(1 for line in lines if 'modified:' in line)
                        new = sum(1 for line in lines if 'new file:' in line)
                        console.print(f"  [dim]→ {modified} modified, {new} new file(s)[/dim]")
                    elif lines:
                        # Generic output summary
                        console.print(f"  [dim]→ Command completed with {len(lines)} line(s) of output[/dim]")
                    else:
                        console.print(f"  [dim]→ Command completed successfully[/dim]")

                    return ToolResult(
                        status=ToolStatus.SUCCESS,
                        output=output if output else error,
                        metadata={"return_code": process.returncode}
                    )
                else:
                    console.print(f"  [dim]→ Command failed with return code {process.returncode}[/dim]")
                    return ToolResult(
                        status=ToolStatus.ERROR,
                        output=output,
                        error=error,
                        metadata={"return_code": process.returncode}
                    )

            except asyncio.TimeoutError:
                process.terminate()
                await process.wait()
                return ToolResult(
                    status=ToolStatus.ERROR,
                    error=f"Command timed out after {timeout} seconds"
                )

        except Exception as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Failed to execute command: {str(e)}"
            )