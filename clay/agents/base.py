"""Base agent class and utilities."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from enum import Enum
import asyncio

from ..tools.base import Tool, ToolResult


class AgentStatus(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    RUNNING_TOOL = "running_tool"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class AgentContext:
    """Context for agent execution."""
    working_directory: str
    conversation_history: List[Dict[str, Any]]
    available_tools: List[Tool]
    metadata: Dict[str, Any]


@dataclass
class AgentResult:
    """Result from agent execution."""
    status: AgentStatus
    output: Optional[str] = None
    error: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class Agent(ABC):
    """Base class for all agents."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.status = AgentStatus.IDLE
        self.context: Optional[AgentContext] = None
        self.tools: Dict[str, Tool] = {}

    def register_tool(self, tool: Tool) -> None:
        """Register a tool for the agent to use."""
        self.tools[tool.name] = tool

    def register_tools(self, tools: List[Tool]) -> None:
        """Register multiple tools."""
        for tool in tools:
            self.register_tool(tool)

    @abstractmethod
    async def think(self, prompt: str, context: AgentContext) -> AgentResult:
        """Process a prompt and decide on actions."""
        pass

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> ToolResult:
        """Execute a tool with given parameters."""
        if tool_name not in self.tools:
            raise ValueError(f"Tool {tool_name} not found")

        tool = self.tools[tool_name]
        return await tool.run(**parameters)

    async def run(self, prompt: str, context: AgentContext) -> AgentResult:
        """Run the agent with a prompt."""
        self.context = context
        self.status = AgentStatus.THINKING

        try:
            result = await self.think(prompt, context)

            if result.tool_calls:
                self.status = AgentStatus.RUNNING_TOOL
                tool_results = []

                for call in result.tool_calls:
                    tool_result = await self.execute_tool(
                        call["name"],
                        call["parameters"]
                    )
                    tool_results.append({
                        "tool": call["name"],
                        "result": tool_result.to_dict()
                    })

                result.metadata = {"tool_results": tool_results}

            self.status = AgentStatus.COMPLETE
            return result

        except Exception as e:
            self.status = AgentStatus.ERROR
            return AgentResult(
                status=AgentStatus.ERROR,
                error=str(e)
            )