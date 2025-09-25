"""Tests for BashTool and BashToolResult."""

import pytest
import json
from pathlib import Path
from clay.tools.bash_tool import BashTool, BashToolResult
from clay.tools.base import ToolStatus


class TestBashToolResult:
    """Test BashToolResult class."""

    def test_bash_tool_result_creation(self):
        """Test creating a BashToolResult."""
        result = BashToolResult(
            status=ToolStatus.SUCCESS,
            command="echo hello",
            return_code=0,
            stdout="hello\n",
            stderr="",
            working_dir="/tmp",
            output="hello\n"
        )

        assert result.status == ToolStatus.SUCCESS
        assert result.command == "echo hello"
        assert result.return_code == 0
        assert result.stdout == "hello\n"
        assert result.stderr == ""
        assert result.working_dir == "/tmp"
        assert result.output == "hello\n"

    def test_to_dict(self):
        """Test converting BashToolResult to dictionary."""
        result = BashToolResult(
            status=ToolStatus.SUCCESS,
            command="ls",
            return_code=0,
            stdout="file1\nfile2\n",
            stderr="",
            working_dir="/home",
            output="file1\nfile2\n"
        )

        result_dict = result.to_dict()

        assert result_dict["status"] == "success"
        assert result_dict["command"] == "ls"
        assert result_dict["return_code"] == 0
        assert result_dict["stdout"] == "file1\nfile2\n"
        assert result_dict["stderr"] == ""
        assert result_dict["working_dir"] == "/home"
        assert result_dict["output"] == "file1\nfile2\n"

    def test_serialize(self):
        """Test full serialization."""
        result = BashToolResult(
            status=ToolStatus.SUCCESS,
            command="echo test",
            return_code=0,
            stdout="test\n",
            stderr="",
            working_dir="/tmp"
        )

        serialized = result.serialize()
        parsed = json.loads(serialized)

        assert parsed["status"] == "success"
        assert parsed["command"] == "echo test"
        assert parsed["return_code"] == 0
        assert parsed["stdout"] == "test\n"

    def test_serialize_human_readable_short_output(self):
        """Test human-readable serialization with short output."""
        result = BashToolResult(
            status=ToolStatus.SUCCESS,
            command="echo hello",
            return_code=0,
            stdout="hello\nworld\n",
            stderr="",
            working_dir="/tmp"
        )

        human_readable = result.serialize_human_readable(max_lines=10)
        parsed = json.loads(human_readable)

        assert parsed["status"] == "success"
        assert parsed["command"] == "echo hello"
        assert parsed["stdout"] == "hello\nworld\n"  # Should not be truncated

    def test_serialize_human_readable_long_output(self):
        """Test human-readable serialization with long output (truncation)."""
        long_output = "\n".join([f"line{i}" for i in range(20)])
        result = BashToolResult(
            status=ToolStatus.SUCCESS,
            command="long command",
            return_code=0,
            stdout=long_output,
            stderr="",
            working_dir="/tmp"
        )

        human_readable = result.serialize_human_readable(max_lines=5)
        parsed = json.loads(human_readable)

        assert parsed["status"] == "success"
        assert "truncated, showing 5 of 20 lines" in parsed["stdout"]
        assert "line0\nline1\nline2\nline3\nline4" in parsed["stdout"]

    def test_get_summary_ls_command(self):
        """Test get_summary for ls command."""
        result = BashToolResult(
            status=ToolStatus.SUCCESS,
            command="ls -la",
            return_code=0,
            stdout="file1\nfile2\nfile3\n",
            stderr=""
        )

        summary = result.get_summary()
        assert summary == "Listed 3 item(s)"

    def test_get_summary_cat_command(self):
        """Test get_summary for cat command."""
        result = BashToolResult(
            status=ToolStatus.SUCCESS,
            command="cat file.txt",
            return_code=0,
            stdout="line1\nline2\n",
            stderr=""
        )

        summary = result.get_summary()
        assert summary == "Displayed 2 line(s)"

    def test_get_summary_grep_command(self):
        """Test get_summary for grep command."""
        result = BashToolResult(
            status=ToolStatus.SUCCESS,
            command="grep pattern file.txt",
            return_code=0,
            stdout="match1\nmatch2\n",
            stderr=""
        )

        summary = result.get_summary()
        assert summary == "Found 2 match(es)"

    def test_get_summary_git_diff_command(self):
        """Test get_summary for git diff command."""
        result = BashToolResult(
            status=ToolStatus.SUCCESS,
            command="git diff",
            return_code=0,
            stdout="--- a/file.txt\n+++ b/file.txt\n-old line\n+new line\n+another line\n",
            stderr=""
        )

        summary = result.get_summary()
        assert summary == "2 addition(s), 1 deletion(s)"

    def test_get_summary_git_status_command(self):
        """Test get_summary for git status command."""
        result = BashToolResult(
            status=ToolStatus.SUCCESS,
            command="git status",
            return_code=0,
            stdout="modified: file1.py\nmodified: file2.py\nnew file: file3.py\n",
            stderr=""
        )

        summary = result.get_summary()
        assert summary == "2 modified, 1 new file(s)"

    def test_get_summary_generic_command(self):
        """Test get_summary for generic command."""
        result = BashToolResult(
            status=ToolStatus.SUCCESS,
            command="custom command",
            return_code=0,
            stdout="output line 1\noutput line 2\n",
            stderr=""
        )

        summary = result.get_summary()
        assert summary == "Command completed with 2 line(s) of output"

    def test_get_summary_no_output(self):
        """Test get_summary for command with no output."""
        result = BashToolResult(
            status=ToolStatus.SUCCESS,
            command="touch file.txt",
            return_code=0,
            stdout="",
            stderr=""
        )

        summary = result.get_summary()
        assert summary == "Command completed successfully"

    def test_get_summary_error(self):
        """Test get_summary for failed command."""
        result = BashToolResult(
            status=ToolStatus.ERROR,
            command="nonexistent-command",
            return_code=127,
            stdout="",
            stderr="command not found"
        )

        summary = result.get_summary()
        assert summary == "Command failed with return code 127"


class TestBashTool:
    """Test BashTool class."""

    @pytest.mark.asyncio
    async def test_bash_tool_creation(self):
        """Test creating a BashTool."""
        tool = BashTool()

        assert tool.name == "bash"
        assert "Execute shell commands" in tool.description
        assert tool.default_timeout == 120

    @pytest.mark.asyncio
    async def test_bash_tool_custom_timeout(self):
        """Test creating BashTool with custom timeout."""
        tool = BashTool(timeout=60)
        assert tool.default_timeout == 60

    def test_get_schema(self):
        """Test BashTool schema."""
        tool = BashTool()
        schema = tool.get_schema()

        assert schema["type"] == "object"
        assert "command" in schema["properties"]
        assert "timeout" in schema["properties"]
        assert "working_dir" in schema["properties"]
        assert schema["required"] == ["command"]

    @pytest.mark.asyncio
    async def test_execute_simple_command(self):
        """Test executing a simple command."""
        tool = BashTool()
        result = await tool.execute("echo 'Hello World'")

        assert isinstance(result, BashToolResult)
        assert result.status == ToolStatus.SUCCESS
        assert result.command == "echo 'Hello World'"
        assert result.return_code == 0
        assert "Hello World" in result.stdout
        assert result.output == result.stdout

    @pytest.mark.asyncio
    async def test_execute_ls_command(self):
        """Test executing ls command."""
        tool = BashTool()
        result = await tool.execute("ls")

        assert isinstance(result, BashToolResult)
        assert result.status == ToolStatus.SUCCESS
        assert result.command == "ls"
        assert result.return_code == 0
        assert result.stdout is not None

    @pytest.mark.asyncio
    async def test_execute_failing_command(self):
        """Test executing a command that fails."""
        tool = BashTool()
        result = await tool.execute("nonexistent-command-12345")

        assert isinstance(result, BashToolResult)
        assert result.status == ToolStatus.ERROR
        assert result.command == "nonexistent-command-12345"
        assert result.return_code != 0
        assert result.stderr is not None

    @pytest.mark.asyncio
    async def test_execute_with_working_dir(self):
        """Test executing command with specific working directory."""
        tool = BashTool()
        # Use /tmp as working directory - should exist on most systems
        result = await tool.execute("pwd", working_dir="/tmp")

        assert isinstance(result, BashToolResult)
        assert result.status == ToolStatus.SUCCESS
        assert result.working_dir == "/tmp"
        assert "/tmp" in result.stdout

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self):
        """Test executing command with custom timeout."""
        tool = BashTool()
        # Use a very short timeout for a quick command
        result = await tool.execute("echo 'quick'", timeout=1)

        assert isinstance(result, BashToolResult)
        assert result.status == ToolStatus.SUCCESS
        assert result.command == "echo 'quick'"

    @pytest.mark.asyncio
    async def test_execute_timeout_error(self):
        """Test command that times out."""
        tool = BashTool()
        # Sleep for longer than timeout
        result = await tool.execute("sleep 2", timeout=1)

        assert isinstance(result, BashToolResult)
        assert result.status == ToolStatus.ERROR
        assert "timed out" in result.error
        assert result.command == "sleep 2"

    @pytest.mark.asyncio
    async def test_validate_parameters(self):
        """Test parameter validation."""
        tool = BashTool()

        # Test missing required parameter
        result = await tool.run()  # No command provided
        assert result.status == ToolStatus.ERROR
        assert "Missing required parameter: command" in result.error

        # Test valid parameters
        result = await tool.run(command="echo test")
        assert result.status == ToolStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_stderr_handling(self):
        """Test handling of stderr output."""
        tool = BashTool()
        # Command that writes to stderr but succeeds
        result = await tool.execute("echo 'error message' >&2; echo 'success'")

        assert isinstance(result, BashToolResult)
        assert result.status == ToolStatus.SUCCESS
        assert "success" in result.stdout
        assert "error message" in result.stderr