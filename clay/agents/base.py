"""Base agent class and utilities."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List
from enum import Enum
import asyncio

from ..tools.base import Tool
from ..runtime import Plan, PlanStep, PlanStatus
from ..trace import trace_operation


class AgentStatus(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    RUNNING_TOOL = "running_tool"
    COMPLETE = "complete"
    ERROR = "error"






class Agent(ABC):
    """Base class for all agents."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.status = AgentStatus.IDLE
        self.tools: Dict[str, Tool] = {}

    def register_tool(self, tool: Tool) -> None:
        """Register a tool for the agent to use."""
        self.tools[tool.name] = tool

    def register_tools(self, tools: List[Tool]) -> None:
        """Register multiple tools."""
        for tool in tools:
            self.register_tool(tool)

    def get_tools_description(self, include_capabilities: bool = False, include_use_cases: bool = False) -> str:
        """Build a description of available tools for use in system prompts."""
        tools_desc = []
        for tool_name, tool in self.tools.items():
            desc = f"- {tool_name}: {tool.description}"

            if include_capabilities and tool.capabilities:
                desc += f"\n  Capabilities: {', '.join(tool.capabilities)}"

            if include_use_cases and tool.use_cases:
                desc += f"\n  Use cases: {', '.join(tool.use_cases)}"

            tools_desc.append(desc)

        return "\n".join(tools_desc)

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
    async def think(self, plan: Plan) -> Plan:
        """Process a plan and decide on actions."""
        pass

    @trace_operation
    async def run(self, prompt: str) -> Plan:
        """Run the agent with a prompt to produce a plan."""
        self.status = AgentStatus.THINKING

        # Print agent status
        from rich.console import Console
        console = Console()
        # Truncate prompt for display
        display_prompt = prompt[:100] + "..." if len(prompt) > 100 else prompt
        console.print(f"\n[bold blue]🤖 {self.name} Agent[/bold blue]: [italic]{display_prompt}[/italic]\n")

        try:
            # Create initial plan with the prompt
            initial_plan = Plan.create_simple_response(prompt, f"Initial prompt: {prompt[:50]}...")
            plan = await self.think(initial_plan)
            self.status = AgentStatus.COMPLETE
            return plan

        except Exception as e:
            self.status = AgentStatus.ERROR
            return Plan.create_error_response(str(e))