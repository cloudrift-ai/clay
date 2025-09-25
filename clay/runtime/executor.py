"""Plan executor for the runtime system."""

import asyncio
from typing import Dict, Any, List
from ..tools.base import Tool, ToolResult, ToolStatus
from ..trace import trace_operation
from .plan import Plan, PlanStep, PlanStatus


class PlanExecutor:
    """Executes plans by running tool steps in the correct order."""

    def __init__(self, tools: Dict[str, Tool]):
        """Initialize executor with available tools."""
        self.tools = tools

    @trace_operation
    async def execute_plan(self, plan: Plan) -> Dict[str, Any]:
        """Execute a complete plan."""
        plan.status = PlanStatus.RUNNING

        try:
            while not plan.is_complete and not plan.has_failed:
                # Get steps that are ready to execute
                executable_steps = plan.get_next_executable_steps()

                if not executable_steps:
                    # No more executable steps - either done or blocked
                    if plan.is_complete:
                        break
                    else:
                        # All remaining steps are blocked by failed dependencies
                        plan.status = PlanStatus.FAILED
                        return {
                            "status": "failed",
                            "error": "Plan execution blocked by failed dependencies",
                            "plan": plan
                        }

                # Execute all ready steps in parallel
                await self._execute_steps_parallel(plan, executable_steps)

            # Determine final status
            if plan.has_failed:
                plan.status = PlanStatus.FAILED
                return {
                    "status": "failed",
                    "error": "One or more steps failed",
                    "plan": plan
                }
            elif plan.is_complete:
                plan.status = PlanStatus.COMPLETED
                return {
                    "status": "success",
                    "plan": plan
                }
            else:
                plan.status = PlanStatus.FAILED
                return {
                    "status": "failed",
                    "error": "Plan execution incomplete",
                    "plan": plan
                }

        except Exception as e:
            plan.status = PlanStatus.FAILED
            return {
                "status": "error",
                "error": str(e),
                "plan": plan
            }

    async def _execute_steps_parallel(self, plan: Plan, step_indices: List[int]):
        """Execute multiple steps in parallel."""
        tasks = []
        for step_index in step_indices:
            task = asyncio.create_task(
                self._execute_single_step(plan, step_index),
                name=f"step_{step_index}"
            )
            tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_single_step(self, plan: Plan, step_index: int):
        """Execute a single step."""
        step = plan.steps[step_index]
        plan.mark_step_running(step_index)

        try:
            # Execute the tool
            result = await self._execute_tool(step.tool_name, step.parameters)

            # Mark step as completed or failed based on result
            if result.status == ToolStatus.SUCCESS:
                plan.mark_step_completed(step_index, result.to_dict())
            else:
                error_msg = result.error or "Tool execution failed"
                plan.mark_step_failed(step_index, error_msg)

        except Exception as e:
            plan.mark_step_failed(step_index, str(e))

    @trace_operation
    async def _execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> ToolResult:
        """Execute a tool with given parameters."""
        if tool_name not in self.tools:
            return ToolResult(
                status=ToolStatus.ERROR,
                error=f"Tool {tool_name} not found"
            )

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