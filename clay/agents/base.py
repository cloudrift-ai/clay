"""Base agent class and utilities."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from ..tools.base import Tool
from ..orchestrator import Plan
from ..trace import trace_operation


class Agent(ABC):
    """Base class for all agents."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.tools: Dict[str, Tool] = {}

    def register_tool(self, tool: Tool) -> None:
        """Register a tool for the agent to use."""
        self.tools[tool.name] = tool

    def register_tools(self, tools: List[Tool]) -> None:
        """Register multiple tools."""
        for tool in tools:
            self.register_tool(tool)

    def get_tools_description(self, include_capabilities: bool = False, include_use_cases: bool = False, include_schema: bool = False) -> str:
        """Build a description of available tools for use in system prompts."""
        tools_desc = []
        for tool_name, tool in self.tools.items():
            desc = tool.get_detailed_description(
                include_capabilities=include_capabilities,
                include_use_cases=include_use_cases,
                include_schema=include_schema
            )
            tools_desc.append(desc)

        return "\n".join(tools_desc)

    def get_json_format_instructions(self) -> str:
        """Get standard JSON format instructions for tool-using agents."""
        return """ALWAYS respond with ONLY valid JSON - no additional text before or after:

JSON FORMAT:

{
    "thought": "I need to analyze the task and decide what tools to use",
    "todo": [
        {
            "tool_name": "tool_name_here",
            "parameters": {
                "param1": "value1",
                "param2": "value2"
            },
            "description": "What this step accomplishes"
        }
    ],
    "output": "Summary of the plan or next actions"
}

CRITICAL PLANNING RULES:
- Steps execute in sequential order (first step, then second step, etc.)
- Files must be created before they can be executed
- Tests must be created before they can be run
- Never plan to run files that don't exist yet
- Plan creation steps before execution steps

If no more tools are needed:
{
    "thought": "Task is complete or no tools needed",
    "todo": [],
    "output": "Final response or information"
}

IMPORTANT: Return ONLY the JSON object above - no explanatory text, no comments, no additional content before or after the JSON."""

    def get_tools_summary(self) -> Dict[str, Dict[str, Any]]:
        """Get a structured summary of available tools."""
        return {
            tool_name: {
                "description": tool.description,
                "capabilities": tool.capabilities,
                "use_cases": tool.use_cases,
                "schema": tool.get_schema()
            }
            for tool_name, tool in self.tools.items()
        }


    @abstractmethod
    async def review_plan(self, plan: Plan, task: str) -> Plan:
        """Review current plan state and update todo list based on completed steps."""
        pass

    @trace_operation
    async def run(self, prompt: str) -> Plan:
        """Run the agent with a prompt to produce an initial plan."""
        try:
            # Create empty plan and let agent populate it
            empty_plan = Plan(todo=[], completed=[])
            plan = await self.review_plan(empty_plan, prompt)
            return plan

        except Exception as e:
            error_plan = Plan.create_error_response(str(e))
            return error_plan