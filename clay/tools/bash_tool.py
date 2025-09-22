"""Bash command execution tool."""

import asyncio
import os
import subprocess
from typing import Optional, Dict, Any
from .base import Tool, ToolResult, ToolStatus


class BashTool(Tool):
    """Execute bash commands."""

    def __init__(self, timeout: int = 120):
        super().__init__(
            name="bash",
            description="Execute bash commands"
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

                if process.returncode == 0:
                    return ToolResult(
                        status=ToolStatus.SUCCESS,
                        output=output if output else error,
                        metadata={"return_code": process.returncode}
                    )
                else:
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