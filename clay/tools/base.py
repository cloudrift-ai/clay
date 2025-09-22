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


class ToolError(Exception):
    """Exception raised by tools."""
    pass


class Tool(ABC):
    """Base class for all tools."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
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