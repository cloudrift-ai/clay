"""Session persistence for Clay CLI."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class SessionManager:
    """Manages conversation sessions for Clay."""

    def __init__(self):
        self.sessions_dir = Path.home() / ".clay" / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.current_session_file = self.sessions_dir / "current.json"

    def create_session(self, initial_message: Optional[str] = None) -> str:
        """Create a new session and return its ID."""
        session_id = str(uuid.uuid4())[:8]
        session_data = {
            "id": session_id,
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "messages": []
        }

        if initial_message:
            session_data["messages"].append({
                "role": "user",
                "content": initial_message,
                "timestamp": datetime.now().isoformat()
            })

        self._save_session(session_id, session_data)
        self._set_current_session(session_id)
        return session_id

    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session data by ID."""
        session_file = self.sessions_dir / f"{session_id}.json"
        if session_file.exists():
            with open(session_file, 'r') as f:
                return json.load(f)
        return None

    def get_current_session(self) -> Optional[Dict]:
        """Get the most recent session."""
        if self.current_session_file.exists():
            with open(self.current_session_file, 'r') as f:
                current_data = json.load(f)
                session_id = current_data.get("session_id")
                if session_id:
                    return self.get_session(session_id)
        return None

    def add_message(self, session_id: str, role: str, content: str):
        """Add a message to a session."""
        session_data = self.get_session(session_id)
        if session_data:
            session_data["messages"].append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat()
            })
            session_data["last_updated"] = datetime.now().isoformat()
            self._save_session(session_id, session_data)

    def list_sessions(self) -> List[Dict]:
        """List all sessions."""
        sessions = []
        for session_file in self.sessions_dir.glob("*.json"):
            if session_file.name != "current.json":
                try:
                    with open(session_file, 'r') as f:
                        session_data = json.load(f)
                        sessions.append({
                            "id": session_data["id"],
                            "created_at": session_data["created_at"],
                            "last_updated": session_data["last_updated"],
                            "message_count": len(session_data["messages"])
                        })
                except json.JSONDecodeError:
                    continue

        # Sort by last updated, most recent first
        sessions.sort(key=lambda x: x["last_updated"], reverse=True)
        return sessions

    def _save_session(self, session_id: str, session_data: Dict):
        """Save session data to file."""
        session_file = self.sessions_dir / f"{session_id}.json"
        with open(session_file, 'w') as f:
            json.dump(session_data, f, indent=2)

    def _set_current_session(self, session_id: str):
        """Set the current session ID."""
        current_data = {"session_id": session_id}
        with open(self.current_session_file, 'w') as f:
            json.dump(current_data, f)