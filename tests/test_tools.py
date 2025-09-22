"""Tests for Clay tools."""

import asyncio
import tempfile
from pathlib import Path
import pytest

from clay.tools import (
    ReadTool, WriteTool, EditTool, GlobTool,
    BashTool, GrepTool, SearchTool,
    ToolStatus
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.mark.asyncio
async def test_write_and_read_tool(temp_dir):
    """Test writing and reading files."""
    write_tool = WriteTool()
    read_tool = ReadTool()

    file_path = str(temp_dir / "test.txt")
    content = "Hello, World!\nThis is a test."

    write_result = await write_tool.run(file_path=file_path, content=content)
    assert write_result.status == ToolStatus.SUCCESS

    read_result = await read_tool.run(file_path=file_path)
    assert read_result.status == ToolStatus.SUCCESS
    assert "Hello, World!" in read_result.output
    assert "This is a test." in read_result.output


@pytest.mark.asyncio
async def test_edit_tool(temp_dir):
    """Test editing files."""
    write_tool = WriteTool()
    edit_tool = EditTool()
    read_tool = ReadTool()

    file_path = str(temp_dir / "edit_test.txt")
    initial_content = "The quick brown fox jumps over the lazy dog."

    await write_tool.run(file_path=file_path, content=initial_content)

    edit_result = await edit_tool.run(
        file_path=file_path,
        old_string="brown fox",
        new_string="red fox"
    )
    assert edit_result.status == ToolStatus.SUCCESS

    read_result = await read_tool.run(file_path=file_path)
    assert "red fox" in read_result.output
    assert "brown fox" not in read_result.output


@pytest.mark.asyncio
async def test_glob_tool(temp_dir):
    """Test file globbing."""
    write_tool = WriteTool()
    glob_tool = GlobTool()

    await write_tool.run(file_path=str(temp_dir / "file1.py"), content="print('1')")
    await write_tool.run(file_path=str(temp_dir / "file2.py"), content="print('2')")
    await write_tool.run(file_path=str(temp_dir / "file3.txt"), content="text")

    result = await glob_tool.run(pattern="*.py", path=str(temp_dir))
    assert result.status == ToolStatus.SUCCESS
    assert "file1.py" in result.output
    assert "file2.py" in result.output
    assert "file3.txt" not in result.output


@pytest.mark.asyncio
async def test_bash_tool():
    """Test bash command execution."""
    bash_tool = BashTool()

    result = await bash_tool.run(command="echo 'Hello from bash'")
    assert result.status == ToolStatus.SUCCESS
    assert "Hello from bash" in result.output

    result = await bash_tool.run(command="exit 1")
    assert result.status == ToolStatus.ERROR


@pytest.mark.asyncio
async def test_grep_tool(temp_dir):
    """Test grep functionality."""
    write_tool = WriteTool()
    grep_tool = GrepTool()

    file1 = temp_dir / "grep1.txt"
    file2 = temp_dir / "grep2.txt"

    await write_tool.run(file_path=str(file1), content="TODO: Fix this\nDone: That")
    await write_tool.run(file_path=str(file2), content="TODO: Another task\nWorking on it")

    result = await grep_tool.run(pattern="TODO", path=str(temp_dir))
    assert result.status == ToolStatus.SUCCESS
    assert "TODO: Fix this" in result.output or "TODO" in result.output
    assert "TODO: Another task" in result.output or "TODO" in result.output


@pytest.mark.asyncio
async def test_search_tool(temp_dir):
    """Test search functionality."""
    write_tool = WriteTool()
    search_tool = SearchTool()

    await write_tool.run(
        file_path=str(temp_dir / "code.py"),
        content="def calculate_sum(a, b):\n    return a + b"
    )

    result = await search_tool.run(query="calculate sum", path=str(temp_dir))
    assert result.status == ToolStatus.SUCCESS