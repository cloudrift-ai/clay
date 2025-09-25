"""Base agent class and utilities."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from enum import Enum
import asyncio

from ..tools.base import Tool, ToolResult, ToolStatus
from ..trace import trace_operation


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
    async def think(self, prompt: str, context: AgentContext) -> AgentResult:
        """Process a prompt and decide on actions."""
        pass

    @trace_operation
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> ToolResult:
        """Execute a tool with given parameters."""
        if tool_name not in self.tools:
            raise ValueError(f"Tool {tool_name} not found")

        tool = self.tools[tool_name]


        # Print tool execution status
        from rich.console import Console
        console = Console()
        console.print(f"[cyan]➤ Executing {tool_name}[/cyan]", end="")

        # Print tool-specific summary
        if tool_name == "bash":
            cmd = parameters.get("command", "")
            console.print(f": [yellow]{cmd[:80]}{'...' if len(cmd) > 80 else ''}[/yellow]")
        elif tool_name == "read":
            console.print(f": [green]{parameters.get('file_path', '')}[/green]")
        elif tool_name == "write":
            console.print(f": [green]{parameters.get('file_path', '')}[/green]")
        elif tool_name == "edit":
            console.print(f": [green]{parameters.get('file_path', '')}[/green]")
        elif tool_name == "glob":
            console.print(f": [yellow]{parameters.get('pattern', '')}[/yellow]")
        elif tool_name == "grep":
            console.print(f": [yellow]{parameters.get('pattern', '')}[/yellow]")
        else:
            console.print()

        result = await tool.run(**parameters)


        return result

    @trace_operation
    async def run(self, prompt: str, context: AgentContext) -> AgentResult:
        """Run the agent with a prompt."""
        self.context = context
        self.status = AgentStatus.THINKING

        # Print agent status
        from rich.console import Console
        console = Console()
        # Truncate prompt for display
        display_prompt = prompt[:100] + "..." if len(prompt) > 100 else prompt
        console.print(f"\n[bold blue]🤖 {self.name} Agent[/bold blue]: [italic]{display_prompt}[/italic]\n")

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