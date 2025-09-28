"""Plan data structures for the runtime system."""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import json


@dataclass
class Step:
    """A single step in an execution plan."""
    tool_name: str
    parameters: Dict[str, Any]
    description: Optional[str] = None
    depends_on: Optional[List[int]] = None  # Indices of steps this depends on
    result: Optional[Dict[str, Any]] = None
    status: Optional[str] = None  # "SUCCESS", "FAILURE", or None (not executed)
    error_message: Optional[str] = None

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
            "status": self.status,
            "error_message": self.error_message
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Step":
        """Create PlanStep from dictionary."""
        return cls(
            tool_name=data.get("tool_name", ""),
            parameters=data.get("parameters", {}),
            description=data.get("description"),
            depends_on=data.get("depends_on", []),
            result=data.get("result"),
            status=data.get("status"),
            error_message=data.get("error_message") or data.get("error")  # Backward compatibility
        )


@dataclass
class Plan:
    """A complete execution plan containing multiple steps."""
    todo: List[Step]  # Steps yet to be executed
    completed: List[Step] = None  # Steps that have been completed
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.completed is None:
            self.completed = []

    @classmethod
    def create_simple_response(cls, message: str, description: Optional[str] = None):
        """Create a plan with a single message step."""
        message_step = Step(
            tool_name="message",
            parameters={"message": message, "category": "info"},
            description=description or "Simple response"
        )
        return cls(
            todo=[message_step],
            completed=[]
        )

    @classmethod
    def create_error_response(cls, error: str, description: Optional[str] = None):
        """Create a plan with an error message step."""
        error_step = Step(
            tool_name="message",
            parameters={"message": error, "category": "error"},
            description=description or "Error response"
        )
        return cls(
            todo=[error_step],
            completed=[]
        )

    @property
    def steps(self) -> List[Step]:
        """Get all steps (completed + todo)."""
        return self.completed + self.todo

    @property
    def is_complete(self) -> bool:
        """Check if all steps are completed."""
        return len(self.todo) == 0

    @property
    def has_failed(self) -> bool:
        """Check if any completed step has failed."""
        return any(step.status == "FAILURE" for step in self.completed)

    def complete_next_step(self, result: Dict[str, Any] = None, error: str = None):
        """Move the next todo step to completed with result or error."""
        if self.todo:
            step = self.todo.pop(0)
            if result is not None:
                step.result = result
                step.status = "SUCCESS"
            if error is not None:
                step.error_message = error
                step.status = "FAILURE"
            self.completed.append(step)
            return step
        return None


    def to_dict(self) -> Dict[str, Any]:
        """Convert Plan to dictionary with optimized structure for KV-cache.

        Places completed steps before todo steps to maintain consistent prefix
        as tasks progress from todo to completed state. This ensures that the
        goal + completed steps form a stable prefix for KV-cache optimization.
        """
        return {
            "completed": [step.to_dict() for step in self.completed],
            "todo": [step.to_dict() for step in self.todo],
            "metadata": self.metadata
        }

    def to_json(self) -> str:
        """Convert Plan to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Plan":
        """Create Plan from dictionary."""
        todo = [Step.from_dict(step_data) for step_data in data.get("todo", [])]
        completed = [Step.from_dict(step_data) for step_data in data.get("completed", [])]

        return cls(
            todo=todo,
            completed=completed,
            metadata=data.get("metadata", {})
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
        todo_data = data.get("todo", [])

        if todo_data:
            # Create plan steps
            steps = []
            for step_data in todo_data:
                step = Step(
                    tool_name=step_data.get("tool_name", ""),
                    parameters=step_data.get("parameters", {}),
                    description=step_data.get("description", "")
                )
                steps.append(step)

            return cls(
                todo=steps,
                completed=[]
            )
        else:
            # No plan needed - just return simple response
            return cls.create_simple_response(
                message=data.get("output", "Task completed")
            )

