"""Tests for conversation management."""

import json
import tempfile
from pathlib import Path
from datetime import datetime
import pytest

from clay.conversation import ConversationManager, Message


def test_add_messages():
    """Test adding messages to conversation."""
    conv = ConversationManager()

    conv.add_user_message("Hello")
    conv.add_assistant_message("Hi there!")

    assert len(conv.messages) == 2
    assert conv.messages[0].role == "user"
    assert conv.messages[0].content == "Hello"
    assert conv.messages[1].role == "assistant"
    assert conv.messages[1].content == "Hi there!"


def test_conversation_history_limit():
    """Test conversation history limit."""
    conv = ConversationManager(max_history=5)

    for i in range(10):
        conv.add_user_message(f"Message {i}")

    assert len(conv.messages) == 5
    assert conv.messages[0].content == "Message 5"
    assert conv.messages[-1].content == "Message 9"


def test_get_history():
    """Test getting conversation history."""
    conv = ConversationManager()

    conv.add_user_message("Question 1")
    conv.add_assistant_message("Answer 1")
    conv.add_user_message("Question 2")
    conv.add_assistant_message("Answer 2")

    history = conv.get_history(limit=2)
    assert len(history) == 2
    assert history[0]["content"] == "Question 2"
    assert history[1]["content"] == "Answer 2"


def test_get_context():
    """Test getting formatted context."""
    conv = ConversationManager()

    conv.add_user_message("What is 2+2?")
    conv.add_assistant_message("2+2 equals 4")

    context = conv.get_context()
    assert "User: What is 2+2?" in context
    assert "Assistant: 2+2 equals 4" in context


def test_save_and_load_session():
    """Test saving and loading conversation sessions."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        conv1 = ConversationManager()
        conv1.add_user_message("Test message", metadata={"key": "value"})
        conv1.add_assistant_message("Test response")

        conv1.save_session(tmp_path)

        conv2 = ConversationManager()
        conv2.load_session(tmp_path)

        assert len(conv2.messages) == 2
        assert conv2.messages[0].content == "Test message"
        assert conv2.messages[0].metadata == {"key": "value"}
        assert conv2.messages[1].content == "Test response"

    finally:
        tmp_path.unlink()


def test_clear_conversation():
    """Test clearing conversation."""
    conv = ConversationManager()

    conv.add_user_message("Message 1")
    conv.add_user_message("Message 2")

    assert len(conv.messages) == 2

    conv.clear()
    assert len(conv.messages) == 0


def test_conversation_summary():
    """Test conversation summarization."""
    conv = ConversationManager()

    conv.add_user_message("Question 1")
    conv.add_assistant_message("Answer 1")
    conv.add_user_message("Question 2")

    summary = conv.summarize()
    assert "Total messages: 3" in summary
    assert "User messages: 2" in summary
    assert "Assistant messages: 1" in summary


def test_message_to_dict():
    """Test message serialization."""
    msg = Message(
        role="user",
        content="Test content",
        metadata={"test": "data"}
    )

    msg_dict = msg.to_dict()
    assert msg_dict["role"] == "user"
    assert msg_dict["content"] == "Test content"
    assert msg_dict["metadata"] == {"test": "data"}
    assert "timestamp" in msg_dict