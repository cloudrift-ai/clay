"""Tests for the message tool."""

import pytest
from clay.tools.message_tool import MessageTool
from clay.tools.base import ToolStatus


@pytest.mark.asyncio
async def test_message_tool_basic():
    """Test basic message tool functionality."""
    tool = MessageTool()

    result = await tool.execute(message="Hello, this is a test message")

    assert result.status == ToolStatus.SUCCESS
    assert "💬 Hello, this is a test message" in result.output
    assert result.metadata["category"] == "info"
    assert result.metadata["raw_message"] == "Hello, this is a test message"


@pytest.mark.asyncio
async def test_message_tool_categories():
    """Test different message categories."""
    tool = MessageTool()

    test_cases = [
        ("info", "💬"),
        ("summary", "📋 Summary:"),
        ("explanation", "💡 Explanation:"),
        ("status", "ℹ️ Status:"),
        ("warning", "⚠️ Warning:"),
        ("error", "❌ Error:")
    ]

    for category, expected_prefix in test_cases:
        result = await tool.execute(message="Test message", category=category)

        assert result.status == ToolStatus.SUCCESS
        assert expected_prefix in result.output
        assert result.metadata["category"] == category


@pytest.mark.asyncio
async def test_message_tool_invalid_category():
    """Test that invalid categories default to info."""
    tool = MessageTool()

    result = await tool.execute(message="Test message", category="invalid_category")

    assert result.status == ToolStatus.SUCCESS
    assert "💬 Test message" in result.output
    assert result.metadata["category"] == "info"


@pytest.mark.asyncio
async def test_message_tool_schema():
    """Test that the tool schema is correct."""
    tool = MessageTool()
    schema = tool.get_schema()

    assert schema["type"] == "object"
    assert "message" in schema["properties"]
    assert "category" in schema["properties"]
    assert schema["required"] == ["message"]
    assert schema["properties"]["category"]["enum"] == ["info", "summary", "explanation", "status", "warning", "error"]


def test_message_tool_attributes():
    """Test tool attributes."""
    tool = MessageTool()

    assert tool.name == "message"
    assert "communicate" in tool.description.lower()
    assert len(tool.capabilities) > 0
    assert len(tool.use_cases) > 0