"""Conversation and context management."""

import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class Message:
    """Represents a conversation message."""
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


class ConversationManager:
    """Manages conversation history and context."""

    def __init__(self, max_history: int = 50):
        self.messages: List[Message] = []
        self.max_history = max_history
        self.context_window = 10
        self.session_file: Optional[Path] = None

    def add_user_message(self, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Add a user message to the conversation."""
        self.add_message("user", content, metadata)

    def add_assistant_message(self, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Add an assistant message to the conversation."""
        self.add_message("assistant", content, metadata)

    def add_system_message(self, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Add a system message to the conversation."""
        self.add_message("system", content, metadata)

    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Add a message to the conversation."""
        message = Message(role=role, content=content, metadata=metadata)
        self.messages.append(message)

        if len(self.messages) > self.max_history:
            self.messages = self.messages[-self.max_history:]

    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """Get conversation history as list of dicts."""
        limit = limit or self.context_window
        recent_messages = self.messages[-limit:] if limit else self.messages

        return [
            {"role": msg.role, "content": msg.content}
            for msg in recent_messages
        ]

    def get_context(self) -> str:
        """Get conversation context as formatted string."""
        context_parts = []

        for msg in self.messages[-self.context_window:]:
            prefix = "User" if msg.role == "user" else "Assistant"
            context_parts.append(f"{prefix}: {msg.content}")

        return "\n\n".join(context_parts)

    def clear(self):
        """Clear conversation history."""
        self.messages = []

    def save_session(self, file_path: Path):
        """Save conversation to file."""
        data = {
            "messages": [msg.to_dict() for msg in self.messages],
            "metadata": {
                "max_history": self.max_history,
                "context_window": self.context_window
            }
        }

        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)

    def load_session(self, file_path: Path):
        """Load conversation from file."""
        if not file_path.exists():
            return

        with open(file_path, 'r') as f:
            data = json.load(f)

        self.messages = []
        for msg_data in data.get("messages", []):
            message = Message(
                role=msg_data["role"],
                content=msg_data["content"],
                timestamp=datetime.fromisoformat(msg_data["timestamp"]),
                metadata=msg_data.get("metadata")
            )
            self.messages.append(message)

        metadata = data.get("metadata", {})
        self.max_history = metadata.get("max_history", self.max_history)
        self.context_window = metadata.get("context_window", self.context_window)

    def summarize(self) -> str:
        """Create a summary of the conversation."""
        if not self.messages:
            return "No conversation yet"

        total_messages = len(self.messages)
        user_messages = sum(1 for m in self.messages if m.role == "user")
        assistant_messages = sum(1 for m in self.messages if m.role == "assistant")

        return (
            f"Conversation Summary:\n"
            f"- Total messages: {total_messages}\n"
            f"- User messages: {user_messages}\n"
            f"- Assistant messages: {assistant_messages}\n"
            f"- Started: {self.messages[0].timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        )