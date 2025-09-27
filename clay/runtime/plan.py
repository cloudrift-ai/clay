"""Plan data structures for the runtime system."""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import json


@dataclass
class PlanStep:
    """A single step in an execution plan."""
    tool_name: str
    parameters: Dict[str, Any]
    description: Optional[str] = None
    depends_on: Optional[List[int]] = None  # Indices of steps this depends on
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.depends_on is None:
            self.depends_on = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert PlanStep to dictionary."""
        return {
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "description": self.description,
            "depends_on": self.depends_on,
            "result": self.result,
            "error": self.error
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanStep":
        """Create PlanStep from dictionary."""
        return cls(
            tool_name=data.get("tool_name", ""),
            parameters=data.get("parameters", {}),
            description=data.get("description"),
            depends_on=data.get("depends_on", []),
            result=data.get("result"),
            error=data.get("error")
        )


@dataclass
class Plan:
    """A complete execution plan containing multiple steps or a simple response."""
    steps: List[PlanStep]
    description: Optional[str] = None
    current_step: int = 0
    metadata: Optional[Dict[str, Any]] = None
    output: Optional[str] = None  # For simple responses without steps
    error: Optional[str] = None   # For plan-level errors

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    @classmethod
    def create_simple_response(cls, output: str, description: Optional[str] = None):
        """Create a plan for simple responses that don't need execution steps."""
        return cls(
            steps=[],
            description=description or "Simple response",
            output=output
        )

    @classmethod
    def create_error_response(cls, error: str, description: Optional[str] = None):
        """Create a plan for error responses."""
        return cls(
            steps=[],
            description=description or "Error response",
            error=error
        )

    @property
    def is_complete(self) -> bool:
        """Check if all steps are completed."""
        return all(step.result is not None for step in self.steps)

    @property
    def has_failed(self) -> bool:
        """Check if any step has failed."""
        return any(step.error is not None for step in self.steps)

    def mark_step_completed(self, step_index: int, result: Dict[str, Any]):
        """Mark a step as completed with result."""
        if 0 <= step_index < len(self.steps):
            self.steps[step_index].result = result

    def mark_step_failed(self, step_index: int, error: str):
        """Mark a step as failed with error."""
        if 0 <= step_index < len(self.steps):
            self.steps[step_index].error = error

    def to_dict(self) -> Dict[str, Any]:
        """Convert Plan to dictionary."""
        return {
            "steps": [step.to_dict() for step in self.steps],
            "description": self.description,
            "current_step": self.current_step,
            "metadata": self.metadata,
            "output": self.output,
            "error": self.error
        }

    def to_json(self) -> str:
        """Convert Plan to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Plan":
        """Create Plan from dictionary."""
        steps = [PlanStep.from_dict(step_data) for step_data in data.get("steps", [])]
        return cls(
            steps=steps,
            description=data.get("description"),
            current_step=data.get("current_step", 0),
            metadata=data.get("metadata", {}),
            output=data.get("output"),
            error=data.get("error")
        )

    @classmethod
    def from_json(cls, json_str: str) -> "Plan":
        """Create Plan from JSON string."""
        try:
            data = json.loads(json_str)
            return cls.from_dict(data)
        except json.JSONDecodeError:
            # If JSON parsing fails, return error response
            return cls.create_error_response(f"Invalid JSON format: {json_str[:100]}...")

    @classmethod
    def from_response(cls, response: str) -> "Plan":
        """Create Plan from LLM response, handling various formats."""
        # Try to extract JSON from markdown code blocks first
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            if end != -1:
                json_content = response[start:end].strip()
                try:
                    data = json.loads(json_content)
                    return cls._create_plan_from_data(data)
                except json.JSONDecodeError:
                    pass

        # Try to parse as direct JSON
        try:
            data = json.loads(response)
            return cls._create_plan_from_data(data)
        except json.JSONDecodeError:
            pass

        # Fallback: return response as simple response plan
        return cls.create_simple_response(response)

    @classmethod
    def _create_plan_from_data(cls, data: dict) -> "Plan":
        """Create Plan from parsed JSON data."""
        plan_data = data.get("plan", [])

        if plan_data:
            # Create plan steps
            steps = []
            for step_data in plan_data:
                step = PlanStep(
                    tool_name=step_data.get("tool_name", ""),
                    parameters=step_data.get("parameters", {}),
                    description=step_data.get("description", "")
                )
                steps.append(step)

            return cls(
                steps=steps,
                description=data.get("thought", "Generated plan"),
                output=data.get("output", "Plan created")
            )
        else:
            # No plan needed - just return simple response
            return cls.create_simple_response(
                output=data.get("output", "Task completed"),
                description=data.get("thought", "Simple response")
            )

