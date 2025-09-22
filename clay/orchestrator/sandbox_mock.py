"""Mock sandbox manager for local execution without containerization."""

import subprocess
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExecResult:
    """Result of command execution."""
    exit_code: int
    stdout: str
    stderr: str
    duration: float
    command: str


class MockSandboxManager:
    """Mock sandbox manager that executes commands locally without isolation."""

    def __init__(self, working_dir: Path):
        self.working_dir = working_dir

    async def detect_stack(self, project_dir: Path) -> Dict[str, Any]:
        """Detect the technology stack and available tools."""
        stack_info = {
            "languages": [],
            "frameworks": [],
            "build_tools": [],
            "test_frameworks": [],
            "formatters": [],
            "linters": []
        }

        # Check for common files and infer stack
        files_to_check = {
            "package.json": {"languages": ["javascript", "typescript"], "build_tools": ["npm", "yarn"]},
            "requirements.txt": {"languages": ["python"], "build_tools": ["pip"]},
            "pyproject.toml": {"languages": ["python"], "build_tools": ["poetry", "pip"]},
            "Cargo.toml": {"languages": ["rust"], "build_tools": ["cargo"]},
            "go.mod": {"languages": ["go"], "build_tools": ["go"]},
            "pom.xml": {"languages": ["java"], "build_tools": ["maven"]},
            "build.gradle": {"languages": ["java", "kotlin"], "build_tools": ["gradle"]},
            "Gemfile": {"languages": ["ruby"], "build_tools": ["bundler"]},
        }

        for file_name, info in files_to_check.items():
            if (project_dir / file_name).exists():
                stack_info["languages"].extend(info.get("languages", []))
                stack_info["build_tools"].extend(info.get("build_tools", []))

        # Detect specific tools
        tool_checks = [
            # Python
            ("black", ["python", "--version"], "formatters"),
            ("ruff", ["--version"], "linters"),
            ("pytest", ["--version"], "test_frameworks"),
            ("mypy", ["--version"], "linters"),
            # JavaScript/TypeScript
            ("prettier", ["--version"], "formatters"),
            ("eslint", ["--version"], "linters"),
            ("jest", ["--version"], "test_frameworks"),
            # Rust
            ("rustfmt", ["--version"], "formatters"),
            ("clippy", ["--version"], "linters"),
            # Go
            ("gofmt", ["-h"], "formatters"),
            ("golangci-lint", ["--version"], "linters"),
        ]

        for tool, check_args, category in tool_checks:
            try:
                result = await self._run_command([tool] + check_args, timeout_s=5)
                if result.exit_code == 0:
                    stack_info[category].append(tool)
            except Exception:
                pass  # Tool not available

        # Remove duplicates
        for key in stack_info:
            stack_info[key] = list(set(stack_info[key]))

        return stack_info

    async def exec(self, cmd: str, cwd: Optional[str] = None, timeout_s: int = 300) -> ExecResult:
        """Execute a command locally."""
        if cwd is None:
            cwd = str(self.working_dir)

        return await self._run_command(cmd.split(), cwd=cwd, timeout_s=timeout_s)

    async def _run_command(self, cmd: List[str], cwd: Optional[str] = None,
                          timeout_s: int = 300) -> ExecResult:
        """Run a command with timeout."""
        start_time = asyncio.get_event_loop().time()

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_s
            )

            duration = asyncio.get_event_loop().time() - start_time

            return ExecResult(
                exit_code=process.returncode,
                stdout=stdout.decode('utf-8', errors='ignore'),
                stderr=stderr.decode('utf-8', errors='ignore'),
                duration=duration,
                command=' '.join(cmd)
            )

        except asyncio.TimeoutError:
            logger.error(f"Command timed out after {timeout_s}s: {' '.join(cmd)}")
            return ExecResult(
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out after {timeout_s}s",
                duration=timeout_s,
                command=' '.join(cmd)
            )

        except Exception as e:
            duration = asyncio.get_event_loop().time() - start_time
            logger.error(f"Command failed: {' '.join(cmd)}: {e}")
            return ExecResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration=duration,
                command=' '.join(cmd)
            )

    async def get_available_commands(self) -> Dict[str, List[str]]:
        """Get available commands by category."""
        commands = {
            "format": [],
            "lint": [],
            "test": [],
            "build": []
        }

        # Common command patterns
        format_commands = [
            ("black .", "python"),
            ("prettier --write .", "javascript"),
            ("rustfmt --edition 2021 **/*.rs", "rust"),
            ("gofmt -w .", "go")
        ]

        lint_commands = [
            ("ruff check .", "python"),
            ("mypy .", "python"),
            ("eslint .", "javascript"),
            ("cargo clippy", "rust"),
            ("golangci-lint run", "go")
        ]

        test_commands = [
            ("pytest", "python"),
            ("python -m pytest", "python"),
            ("npm test", "javascript"),
            ("yarn test", "javascript"),
            ("cargo test", "rust"),
            ("go test ./...", "go")
        ]

        build_commands = [
            ("python -m build", "python"),
            ("npm run build", "javascript"),
            ("yarn build", "javascript"),
            ("cargo build", "rust"),
            ("go build", "go")
        ]

        # Check which commands are available
        all_checks = [
            (format_commands, "format"),
            (lint_commands, "lint"),
            (test_commands, "test"),
            (build_commands, "build")
        ]

        for cmd_list, category in all_checks:
            for cmd, lang in cmd_list:
                try:
                    # Try to run with --help or --version to check availability
                    base_cmd = cmd.split()[0]
                    check_result = await self._run_command([base_cmd, "--help"], timeout_s=5)
                    if check_result.exit_code == 0 or "unrecognized arguments" in check_result.stderr:
                        commands[category].append(cmd)
                except Exception:
                    pass

        return commands