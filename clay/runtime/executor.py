"""Plan executor for the runtime system."""

import asyncio
from typing import Dict, Any, List
from ..tools.base import Tool, ToolResult, ToolStatus
from ..trace import trace_operation
from .plan import Plan, Step


class PlanExecutor:
    """Executes plans by running tool steps in the correct order."""

    def __init__(self, tools: Dict[str, Tool]):
        """Initialize executor with available tools."""
        self.tools = tools

    @trace_operation
    async def execute_plan(self, plan: Plan) -> Dict[str, Any]:
        """Execute a complete plan."""
        try:
            # Execute all steps sequentially
            for i, step in enumerate(plan.steps):
                await self._execute_single_step(plan, i)

            # Determine final status
            if plan.has_failed:
                return {
                    "status": "failed",
                    "error": "One or more steps failed",
                    "plan": plan
                }
            elif plan.is_complete:
                return {
                    "status": "success",
                    "plan": plan
                }
            else:
                return {
                    "status": "failed",
                    "error": "Plan execution incomplete",
                    "plan": plan
                }

        except Exception as e:
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

        result = await tool.run(**parameters)

        # Add execution info to result metadata for display purposes
        if not result.metadata:
            result.metadata = {}
        result.metadata["tool_name"] = tool_name

        # Add tool-specific execution info
        if tool_name == "bash":
            cmd = parameters.get("command", "")
            result.metadata["execution_info"] = f"➤ Executing {tool_name}: {cmd[:80]}{'...' if len(cmd) > 80 else ''}"
        elif tool_name in ["read", "write", "edit"]:
            file_path = parameters.get('file_path', '')
            result.metadata["execution_info"] = f"➤ Executing {tool_name}: {file_path}"
        elif tool_name in ["glob", "grep"]:
            pattern = parameters.get('pattern', '')
            result.metadata["execution_info"] = f"➤ Executing {tool_name}: {pattern}"
        else:
            result.metadata["execution_info"] = f"➤ Executing {tool_name}"
        return result