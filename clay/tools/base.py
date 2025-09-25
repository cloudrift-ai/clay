"""Base classes for the tool system."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from dataclasses import dataclass
from enum import Enum
import json


class ToolStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"
    BLOCKED = "blocked"


@dataclass
class ToolResult:
    """Base class for tool results."""
    status: ToolStatus
    output: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata
        }

    def serialize(self) -> str:
        """Serialize the full tool result."""
        return json.dumps(self.to_dict(), indent=2)

    def serialize_human_readable(self, max_lines: int = 10) -> str:
        """Serialize a human-readable version with limited output."""
        result = {
            "status": self.status.value,
            "error": self.error,
            "metadata": self.metadata
        }

        if self.output:
            lines = self.output.splitlines()
            if len(lines) <= max_lines:
                result["output"] = self.output
            else:
                truncated_output = '\n'.join(lines[:max_lines])
                result["output"] = truncated_output + f"\n... (truncated, showing {max_lines} of {len(lines)} lines)"

        return json.dumps(result, indent=2)


class ToolError(Exception):
    """Exception raised by tools."""
    pass


class Tool(ABC):
    """Base class for all tools."""

    def __init__(self, name: str, description: str, capabilities: Optional[List[str]] = None, use_cases: Optional[List[str]] = None):
        self.name = name
        self.description = description
        self.capabilities = capabilities or []
        self.use_cases = use_cases or []
        self.parameters: Dict[str, Any] = {}

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters."""
        pass

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """Get JSON schema for tool parameters."""
        pass

    def validate_parameters(self, params: Dict[str, Any]) -> None:
        """Validate tool parameters against schema."""
        required = self.get_schema().get("required", [])
        for field in required:
            if field not in params:
                raise ToolError(f"Missing required parameter: {field}")

    async def run(self, **kwargs) -> ToolResult:
        """Run the tool with validation."""
        try:
            self.validate_parameters(kwargs)
            return await self.execute(**kwargs)
        except ToolError as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=str(e)
            )
        except Exception as e:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Unexpected error: {str(e)}"
            )