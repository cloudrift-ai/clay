"""Base agent class and utilities."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from enum import Enum
import asyncio

from ..tools.base import Tool, ToolResult, ToolStatus
from ..trace import trace_operation, trace_event, trace_error, trace_agent_action


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
        with trace_operation("Agent", "execute_tool",
                           agent_name=self.name,
                           tool_name=tool_name,
                           parameters=list(parameters.keys())):

            if tool_name not in self.tools:
                raise ValueError(f"Tool {tool_name} not found")

            tool = self.tools[tool_name]

            trace_event("Tool", "execution_started",
                       agent=self.name,
                       tool_name=tool_name,
                       parameter_count=len(parameters))

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

            trace_event("Tool", "execution_completed",
                       agent=self.name,
                       tool_name=tool_name,
                       success=(result.status == ToolStatus.SUCCESS),
                       output_length=len(result.output or ""))

            return result

    async def run(self, prompt: str, context: AgentContext) -> AgentResult:
        """Run the agent with a prompt."""
        with trace_operation("Agent", "run",
                           agent_name=self.name,
                           prompt_length=len(prompt),
                           has_tools=len(self.tools) > 0):

            trace_agent_action(self.name, "started", prompt_length=len(prompt))

            self.context = context
            self.status = AgentStatus.THINKING

            # Print agent status
            from rich.console import Console
            console = Console()
            # Truncate prompt for display
            display_prompt = prompt[:100] + "..." if len(prompt) > 100 else prompt
            console.print(f"\n[bold blue]🤖 {self.name} Agent[/bold blue]: [italic]{display_prompt}[/italic]\n")

            try:
                trace_agent_action(self.name, "thinking")
                result = await self.think(prompt, context)

                if result.tool_calls:
                    trace_agent_action(self.name, "executing_tools",
                                     tool_count=len(result.tool_calls))
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
                trace_agent_action(self.name, "completed",
                                 output_length=len(result.output or ""))
                return result

            except Exception as e:
                self.status = AgentStatus.ERROR
                trace_error("Agent", "execution_failed", e, agent_name=self.name)
                return AgentResult(
                    status=AgentStatus.ERROR,
                    error=str(e)
                )