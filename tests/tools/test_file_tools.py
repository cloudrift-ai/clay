"""Tests for file manipulation tools."""

import os
import tempfile
import pytest
import asyncio
from pathlib import Path

from clay.tools.file_tools import ReadTool, WriteTool, UpdateTool, FileToolResult
from clay.tools.base import ToolStatus


class TestReadTool:
    """Test cases for the ReadTool."""

    @pytest.mark.asyncio
    async def test_read_existing_file(self, tmp_path):
        """Test reading an existing file."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_content = "Line 1\nLine 2\nLine 3\n"
        test_file.write_text(test_content)

        # Test reading
        read_tool = ReadTool()
        result = await read_tool.execute(file_path=str(test_file))

        assert result.status == ToolStatus.SUCCESS
        assert result.lines_affected == 3
        assert result.operation == "read"
        assert "Line 1" in result.output
        assert "Line 2" in result.output
        assert "Line 3" in result.output
        # Check line numbers are included
        assert "1→" in result.output
        assert "2→" in result.output
        assert "3→" in result.output

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self):
        """Test reading a non-existent file."""
        read_tool = ReadTool()
        result = await read_tool.execute(file_path="/nonexistent/file.txt")

        assert result.status == ToolStatus.ERROR
        assert "File not found" in result.error
        assert result.operation == "read"

    @pytest.mark.asyncio
    async def test_read_file_with_line_range(self, tmp_path):
        """Test reading a file with specific line range."""
        # Create a test file with multiple lines
        test_file = tmp_path / "multiline.txt"
        lines = [f"Line {i}\n" for i in range(1, 11)]
        test_file.write_text(''.join(lines))

        # Read lines 3-5
        read_tool = ReadTool()
        result = await read_tool.execute(
            file_path=str(test_file),
            start_line=3,
            end_line=5
        )

        assert result.status == ToolStatus.SUCCESS
        assert result.lines_affected == 3  # Lines 3, 4, and 5 (end_line is inclusive)
        assert "Line 3" in result.output
        assert "Line 4" in result.output
        assert "Line 5" in result.output
        assert "Line 2" not in result.output
        assert "Line 6" not in result.output

    @pytest.mark.asyncio
    async def test_read_file_encoding(self, tmp_path):
        """Test reading a file with different encoding."""
        test_file = tmp_path / "encoded.txt"
        test_content = "Hello World! 你好世界!"
        test_file.write_text(test_content, encoding='utf-8')

        read_tool = ReadTool()
        result = await read_tool.execute(
            file_path=str(test_file),
            encoding='utf-8'
        )

        assert result.status == ToolStatus.SUCCESS
        assert "Hello World!" in result.output
        assert "你好世界!" in result.output


class TestWriteTool:
    """Test cases for the WriteTool."""

    @pytest.mark.asyncio
    async def test_write_new_file(self, tmp_path):
        """Test writing to a new file."""
        test_file = tmp_path / "new_file.txt"
        test_content = "This is test content.\nWith multiple lines.\n"

        write_tool = WriteTool()
        result = await write_tool.execute(
            file_path=str(test_file),
            content=test_content
        )

        assert result.status == ToolStatus.SUCCESS
        assert result.lines_affected == 2
        assert result.operation == "write"
        assert test_file.exists()
        assert test_file.read_text() == test_content

    @pytest.mark.asyncio
    async def test_overwrite_existing_file(self, tmp_path):
        """Test overwriting an existing file."""
        test_file = tmp_path / "existing.txt"
        test_file.write_text("Old content")

        new_content = "New content\nCompletely replaced\n"
        write_tool = WriteTool()
        result = await write_tool.execute(
            file_path=str(test_file),
            content=new_content
        )

        assert result.status == ToolStatus.SUCCESS
        assert result.lines_affected == 2
        assert test_file.read_text() == new_content

    @pytest.mark.asyncio
    async def test_write_with_directory_creation(self, tmp_path):
        """Test writing a file with automatic directory creation."""
        test_file = tmp_path / "subdir" / "nested" / "file.txt"
        test_content = "Content in nested directory"

        write_tool = WriteTool()
        result = await write_tool.execute(
            file_path=str(test_file),
            content=test_content,
            create_dirs=True
        )

        assert result.status == ToolStatus.SUCCESS
        assert test_file.exists()
        assert test_file.parent.exists()
        assert test_file.read_text() == test_content

    @pytest.mark.asyncio
    async def test_write_console_summary(self, tmp_path):
        """Test the console summary output for write operations."""
        test_file = tmp_path / "summary_test.txt"
        write_tool = WriteTool()
        result = await write_tool.execute(
            file_path=str(test_file),
            content="Test"
        )

        summary = result.console_summary()
        assert "✅" in summary
        assert "Created" in summary
        assert "summary_test.txt" in summary


class TestUpdateTool:
    """Test cases for the UpdateTool."""

    @pytest.mark.asyncio
    async def test_update_single_occurrence(self, tmp_path):
        """Test updating a single occurrence in a file."""
        test_file = tmp_path / "update.txt"
        original_content = """def hello():
    print("Hello")
    return "success"

def goodbye():
    print("Goodbye")
    return "done"
"""
        test_file.write_text(original_content)

        update_tool = UpdateTool()
        result = await update_tool.execute(
            file_path=str(test_file),
            old_content='    print("Hello")',
            new_content='    print("Hello, World!")'
        )

        assert result.status == ToolStatus.SUCCESS
        assert result.lines_affected == 1
        updated_content = test_file.read_text()
        assert 'print("Hello, World!")' in updated_content
        assert 'print("Goodbye")' in updated_content

    @pytest.mark.asyncio
    async def test_update_multiple_occurrences(self, tmp_path):
        """Test updating multiple occurrences with replace_all."""
        test_file = tmp_path / "multi_update.txt"
        original_content = """x = 10
y = 10
z = 10
"""
        test_file.write_text(original_content)

        update_tool = UpdateTool()
        result = await update_tool.execute(
            file_path=str(test_file),
            old_content="10",
            new_content="20",
            replace_all=True
        )

        assert result.status == ToolStatus.SUCCESS
        assert result.lines_affected == 3
        updated_content = test_file.read_text()
        assert updated_content == """x = 20
y = 20
z = 20
"""

    @pytest.mark.asyncio
    async def test_update_nonexistent_file(self):
        """Test updating a non-existent file."""
        update_tool = UpdateTool()
        result = await update_tool.execute(
            file_path="/nonexistent/file.txt",
            old_content="old",
            new_content="new"
        )

        assert result.status == ToolStatus.ERROR
        assert "File not found" in result.error

    @pytest.mark.asyncio
    async def test_update_content_not_found(self, tmp_path):
        """Test updating when old content is not found."""
        test_file = tmp_path / "no_match.txt"
        test_file.write_text("Some content here")

        update_tool = UpdateTool()
        result = await update_tool.execute(
            file_path=str(test_file),
            old_content="not present",
            new_content="replacement"
        )

        assert result.status == ToolStatus.ERROR
        assert "Old content not found" in result.error

    @pytest.mark.asyncio
    async def test_update_diff_output(self, tmp_path):
        """Test the diff output format."""
        test_file = tmp_path / "diff_test.py"
        original_content = """def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
"""
        test_file.write_text(original_content)

        update_tool = UpdateTool()
        result = await update_tool.execute(
            file_path=str(test_file),
            old_content="def subtract(a, b):\n    return a - b",
            new_content='def subtract(a, b):\n    """Subtract b from a."""\n    return a - b'
        )

        assert result.status == ToolStatus.SUCCESS
        assert "⏺ Update" in result.output
        assert "additions" in result.output
        # Check that the diff shows the added docstring
        assert '"""Subtract b from a."""' in test_file.read_text()

    @pytest.mark.asyncio
    async def test_update_preserves_whitespace(self, tmp_path):
        """Test that update preserves exact whitespace."""
        test_file = tmp_path / "whitespace.py"
        # Use spaces for indentation
        original_content = "def func():\n    x = 1\n    return x\n"
        test_file.write_text(original_content)

        update_tool = UpdateTool()
        result = await update_tool.execute(
            file_path=str(test_file),
            old_content="    x = 1",
            new_content="    x = 2"
        )

        assert result.status == ToolStatus.SUCCESS
        updated_content = test_file.read_text()
        assert "    x = 2" in updated_content
        # Ensure whitespace is preserved
        assert updated_content == "def func():\n    x = 2\n    return x\n"


class TestFileToolResult:
    """Test cases for FileToolResult class."""

    def test_file_tool_result_success(self):
        """Test FileToolResult for successful operations."""
        result = FileToolResult(
            status=ToolStatus.SUCCESS,
            output="Operation successful",
            file_path="/path/to/file.txt",
            lines_affected=5,
            operation="read"
        )

        assert result.status == ToolStatus.SUCCESS
        assert result.file_path == "/path/to/file.txt"
        assert result.lines_affected == 5
        assert result.operation == "read"

        # Test console summary
        summary = result.console_summary()
        assert "✅" in summary
        assert "Read" in summary
        assert "/path/to/file.txt" in summary
        assert "5" in summary

    def test_file_tool_result_error(self):
        """Test FileToolResult for error cases."""
        result = FileToolResult(
            status=ToolStatus.ERROR,
            error="Something went wrong",
            file_path="/path/to/file.txt",
            operation="write"
        )

        assert result.status == ToolStatus.ERROR
        assert result.error == "Something went wrong"

        # Test console summary
        summary = result.console_summary()
        assert "❌" in summary
        assert "File operation failed" in summary
        assert "Something went wrong" in summary

    def test_file_tool_result_to_dict(self):
        """Test FileToolResult serialization to dict."""
        result = FileToolResult(
            status=ToolStatus.SUCCESS,
            output="Test output",
            file_path="/test/file.txt",
            lines_affected=10,
            operation="update",
            metadata={"encoding": "utf-8"}
        )

        result_dict = result.to_dict()
        assert result_dict["status"] == "success"
        assert result_dict["output"] == "Test output"
        assert result_dict["file_path"] == "/test/file.txt"
        assert result_dict["lines_affected"] == 10
        assert result_dict["operation"] == "update"
        assert result_dict["metadata"]["encoding"] == "utf-8"


class TestToolIntegration:
    """Integration tests for file tools working together."""

    @pytest.mark.asyncio
    async def test_write_read_update_workflow(self, tmp_path):
        """Test a complete workflow: write, read, update."""
        test_file = tmp_path / "workflow.py"

        # Step 1: Write initial file
        write_tool = WriteTool()
        write_result = await write_tool.execute(
            file_path=str(test_file),
            content="def hello():\n    return 'Hello'\n"
        )
        assert write_result.status == ToolStatus.SUCCESS

        # Step 2: Read the file
        read_tool = ReadTool()
        read_result = await read_tool.execute(file_path=str(test_file))
        assert read_result.status == ToolStatus.SUCCESS
        assert "def hello():" in read_result.output

        # Step 3: Update the file
        update_tool = UpdateTool()
        update_result = await update_tool.execute(
            file_path=str(test_file),
            old_content="    return 'Hello'",
            new_content="    return 'Hello, World!'"
        )
        assert update_result.status == ToolStatus.SUCCESS

        # Step 4: Read again to verify update
        verify_result = await read_tool.execute(file_path=str(test_file))
        assert verify_result.status == ToolStatus.SUCCESS
        assert "Hello, World!" in verify_result.output

    @pytest.mark.asyncio
    async def test_tools_handle_unicode(self, tmp_path):
        """Test that all tools handle Unicode content correctly."""
        test_file = tmp_path / "unicode.txt"
        unicode_content = "Hello 世界! 🌍 Привет мир!"

        # Write Unicode content
        write_tool = WriteTool()
        write_result = await write_tool.execute(
            file_path=str(test_file),
            content=unicode_content
        )
        assert write_result.status == ToolStatus.SUCCESS

        # Read Unicode content
        read_tool = ReadTool()
        read_result = await read_tool.execute(file_path=str(test_file))
        assert read_result.status == ToolStatus.SUCCESS
        assert "世界" in read_result.output
        assert "🌍" in read_result.output
        assert "Привет" in read_result.output

        # Update Unicode content
        update_tool = UpdateTool()
        update_result = await update_tool.execute(
            file_path=str(test_file),
            old_content="世界",
            new_content="ワールド"
        )
        assert update_result.status == ToolStatus.SUCCESS

        # Verify update
        final_content = test_file.read_text()
        assert "ワールド" in final_content
        assert "世界" not in final_content