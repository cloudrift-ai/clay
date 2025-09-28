"""Base classes for the tool system."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from dataclasses import dataclass
from enum import Enum
import json
from ..trace import trace_operation


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

    def get_example_usage(self) -> str:
        """Get example usage for the tool. Override in subclasses for tool-specific examples."""
        schema = self.get_schema()
        properties = schema.get("properties", {})
        required_fields = schema.get("required", [])

        # Generate a basic example based on schema
        example_params = {}
        for field_name, field_info in properties.items():
            field_type = field_info.get("type", "string")
            if field_type == "string":
                example_params[field_name] = f"example_{field_name}"
            elif field_type == "integer":
                example_params[field_name] = 30
            elif field_type == "boolean":
                example_params[field_name] = True
            else:
                example_params[field_name] = f"<{field_type}_value>"

        return json.dumps({
            "tool_name": self.name,
            "parameters": example_params,
            "description": f"Example usage of {self.name} tool"
        }, indent=2)

    def get_detailed_description(self, include_capabilities: bool = False, include_use_cases: bool = False, include_schema: bool = False) -> str:
        """Get a detailed description of this tool for use in system prompts."""
        desc = f"- {self.name}: {self.description}"

        if include_capabilities and self.capabilities:
            desc += f"\n  Capabilities: {', '.join(self.capabilities)}"

        if include_use_cases and self.use_cases:
            desc += f"\n  Use cases: {', '.join(self.use_cases)}"

        if include_schema:
            schema = self.get_schema()
            desc += f"\n  Parameters: {self._format_schema(schema)}"

            # Add example usage
            example = self.get_example_usage()
            desc += f"\n  Example: {example}"

        return desc

    def _format_schema(self, schema: dict) -> str:
        """Format JSON schema for human-readable display."""
        if not schema or "properties" not in schema:
            return "None"

        properties = schema["properties"]
        required = schema.get("required", [])

        formatted_props = []
        for prop_name, prop_info in properties.items():
            prop_type = prop_info.get("type", "unknown")
            prop_desc = prop_info.get("description", "")
            required_marker = " (required)" if prop_name in required else " (optional)"

            # Add default value if present
            default_info = ""
            if "default" in prop_info:
                default_info = f" [default: {prop_info['default']}]"

            # Add examples if present
            examples_info = ""
            if "examples" in prop_info:
                examples = prop_info["examples"]
                if len(examples) <= 3:
                    examples_info = f" [examples: {', '.join(map(str, examples))}]"
                else:
                    examples_info = f" [examples: {', '.join(map(str, examples[:2]))}, ...]"

            formatted_props.append(f"{prop_name}: {prop_type}{required_marker} - {prop_desc}{default_info}{examples_info}")

        return "; ".join(formatted_props)

    def validate_parameters(self, params: Dict[str, Any]) -> None:
        """Validate tool parameters against schema."""
        required = self.get_schema().get("required", [])
        for field in required:
            if field not in params:
                raise ToolError(f"Missing required parameter: {field}")

    @trace_operation
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