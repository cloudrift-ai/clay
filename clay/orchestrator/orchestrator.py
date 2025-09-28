"""Clay orchestrator that uses agents to create plans and runtime to execute them."""

from pathlib import Path
from typing import Dict, Any, Optional
import json
import sys
import os
from datetime import datetime

from ..agents.llm_agent import LLMAgent
from ..agents.coding_agent import CodingAgent
from ..runtime import Plan
from ..llm import completion
from ..tools.base import ToolStatus
from ..trace import trace_operation, clear_trace, save_trace_file, set_session_id


class ClayOrchestrator:
    """Orchestrator that coordinates agents and plan execution."""

    def __init__(self, traces_dir: Optional[Path] = None):
        """Initialize the orchestrator with all available agents.

        Args:
            traces_dir: Directory to save traces and plan files. If None, uses current directory's _trace/
        """
        # Initialize all available agents
        self.agents = {
            'llm_agent': LLMAgent(),
            'coding_agent': CodingAgent()
        }

        # Create tool registries for each agent
        self.agent_tools = {}
        for agent_name, agent in self.agents.items():
            self.agent_tools[agent_name] = agent.tools if hasattr(agent, 'tools') else {}

        # Set traces directory
        self.traces_dir = traces_dir

        # Terminal state for todo list management
        self._todo_lines_count = 0
        self._supports_ansi = self._check_ansi_support()

    @trace_operation
    async def select_agent(self, goal: str) -> str:
        """Use LLM to select the best agent for the task."""
        agent_descriptions = self._build_agent_descriptions()
        available_agent_names = list(self.agents.keys())

        system_prompt = f"""You are an agent router that selects the best agent for a given task.

Available agents:
{agent_descriptions}

Choose the most appropriate agent for the task. Respond with ONLY the agent name from: {', '.join(available_agent_names)}.

Selection criteria are automatically derived from each agent's description and capabilities."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Task: {goal}"}
        ]

        response = await completion(messages=messages, temperature=0.1)
        selected_agent = response['choices'][0]['message']['content'].strip().lower()

        # Validate and default to first available agent if unclear
        if selected_agent not in self.agents:
            # Default to first available agent for ambiguous cases
            selected_agent = list(self.agents.keys())[0]

        return selected_agent

    def _save_plan_to_trace_dir(self, plan: Plan, iteration: int, goal: str) -> Path:
        """Save the plan to the traces directory for debugging."""
        # Use configured traces directory or default to current directory's _trace
        if self.traces_dir:
            trace_dir = self.traces_dir
        else:
            trace_dir = Path.cwd() / "_trace"
        trace_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp and iteration
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"plan_iter_{iteration:03d}_{timestamp}.json"
        filepath = trace_dir / filename

        # Create plan data with metadata
        plan_data = {
            "iteration": iteration,
            "timestamp": datetime.now().isoformat(),
            "goal": goal,
            "plan": plan.to_dict()
        }

        # Save to file
        with open(filepath, 'w') as f:
            json.dump(plan_data, f, indent=2)

        return filepath

    def _build_agent_descriptions(self) -> str:
        """Build a description of available agents."""
        descriptions = []
        for agent_name, agent in self.agents.items():
            description = f"- {agent_name}: {agent.description}"
            if hasattr(agent, 'capabilities'):
                description += f"\n  Capabilities: {', '.join(agent.capabilities)}"
            descriptions.append(description)
        return "\n\n".join(descriptions)

    def _check_ansi_support(self) -> bool:
        """Check if terminal supports ANSI escape sequences."""
        return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty() and os.getenv('TERM') != 'dumb'

    def _clear_todo_lines(self) -> None:
        """Clear the previously printed todo list lines."""
        if self._supports_ansi and self._todo_lines_count > 0:
            # Move cursor up and clear lines
            for _ in range(self._todo_lines_count):
                sys.stdout.write('\033[A')  # Move cursor up one line
                sys.stdout.write('\033[K')  # Clear line
            sys.stdout.flush()
            self._todo_lines_count = 0

    def _print_tool_execution(self, tool: Any, tool_name: str, parameters: Dict[str, Any], result) -> None:
        """Print console-friendly summary of tool execution in Claude Code format."""
        # Clear any existing todo list first
        self._clear_todo_lines()

        # Get the tool's formatted display
        tool_call = tool.get_tool_call_display(parameters)
        print(tool_call)

        # Print the result summary with proper formatting
        if hasattr(result, 'get_formatted_output'):
            output = result.get_formatted_output()
        else:
            # Default formatting for results without custom formatter
            if result.status == ToolStatus.SUCCESS:
                output = result.output or "Success"
            else:
                output = f"Error: {result.error or 'Unknown error'}"

        # Format and truncate output
        if output:
            lines = output.splitlines()
            if len(lines) > 10:
                # Show first 9 lines and indicate more
                formatted_lines = lines[:9]
                remaining = len(lines) - 9
                formatted_lines.append(f"… +{remaining} lines (ctrl+o to see all)")
                output = '\n'.join(formatted_lines)

            # Indent output lines
            indented_output = '\n'.join(f"  {line}" if i == 0 else f"     {line}"
                                       for i, line in enumerate(output.splitlines()))

            # Add the ⎿ character for the first line
            if indented_output:
                indented_output = "  ⎿" + indented_output[2:]

            print(indented_output)

    def _print_todo_list_at_bottom(self, plan: Plan) -> None:
        """Print compact todo list that stays at the bottom."""
        lines = []

        if not plan.todo:
            lines.append("📋 ✅ All tasks completed!")
        else:
            # Show current task and next few
            current_task = plan.todo[0].description
            lines.append(f"📋 [{len(plan.todo)} remaining] Current: {current_task}")

            if len(plan.todo) > 1:
                next_task = plan.todo[1].description
                lines.append(f"   Next: {next_task}")

            if len(plan.todo) > 2:
                lines.append(f"   +{len(plan.todo) - 2} more tasks...")

        # Print separator and todo lines
        lines.insert(0, "-" * 60)
        lines.append("-" * 60)

        for line in lines:
            print(line)

        # Track lines for clearing later
        self._todo_lines_count = len(lines)

    def _print_initial_todo_list(self, plan: Plan) -> None:
        """Print the initial todo list."""
        print("\n" + "="*60)
        print(f"📋 PLANNED TASKS ({len(plan.todo)} total):")
        print("="*60)

        for i, step in enumerate(plan.todo[:8], 1):  # Show first 8 tasks
            print(f"  {i}. {step.description}")

        if len(plan.todo) > 8:
            print(f"  ... and {len(plan.todo) - 8} more tasks")

        print("="*60)
        print("🚀 Starting execution...\n")

    def _print_completion_status(self, plan: Plan) -> None:
        """Print final completion status."""
        if not plan.todo:
            print(f"\n🎉 SUCCESS: All {len(plan.completed)} tasks completed!")
        else:
            print(f"\n⚠️  INCOMPLETE: {len(plan.completed)} completed, {len(plan.todo)} remaining")

    @trace_operation
    async def process_task(self, goal: str) -> Plan:
        """Process a task using iterative agent planning and execution.

        The process:
        1. Agent creates initial plan
        2. Execute next step from todo list
        3. Agent reviews plan with completed step and updates todo list
        4. Repeat until todo list is empty
        """

        working_dir = Path.cwd()
        if not working_dir.exists():
            return Plan.create_error_response(
                error=f"Working directory {working_dir} does not exist",
                description="Working directory validation failed"
            )

        try:
            # Set up tracing if traces directory is configured
            session_id = None
            if self.traces_dir:
                # Clear previous traces and set up new session
                clear_trace()
                session_id = f"orchestrator_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                set_session_id(session_id)

            # Select the best agent for the task
            selected_agent_name = await self.select_agent(goal)
            selected_agent = self.agents[selected_agent_name]
            agent_tools = self.agent_tools[selected_agent_name]

            # Get initial plan from agent
            plan = await selected_agent.run(goal)

            # Print initial task info only
            print(f"\n🎯 Task: {goal}")
            print(f"🤖 Agent: {selected_agent_name}")
            print()  # Add blank line before tool executions start

            # Save initial plan (iteration 0)
            self._save_plan_to_trace_dir(plan, 0, goal)

            # Iterative execution loop
            max_iterations = 50  # Safety limit
            iteration = 0

            # Print initial todo list
            self._print_initial_todo_list(plan)

            # Print initial compact todo list at bottom
            self._print_todo_list_at_bottom(plan)

            while plan.todo and iteration < max_iterations:
                iteration += 1

                # Execute the next step
                next_step = plan.todo[0]
                tool_name = next_step.tool_name
                parameters = next_step.parameters

                if tool_name in agent_tools:
                    tool = agent_tools[tool_name]
                    result = await tool.run(**parameters)

                    # Print console summary of the tool execution
                    self._print_tool_execution(tool, tool_name, parameters, result)

                    # Move step to completed with result
                    if result.status == ToolStatus.SUCCESS:
                        plan.complete_next_step(result=result.to_dict())
                    else:
                        error_msg = result.error or "Tool execution failed"
                        plan.complete_next_step(error=error_msg)
                else:
                    error_msg = f"Tool {tool_name} not found"
                    print(f"\n❌ Tool execution failed: {error_msg}")
                    plan.complete_next_step(error=error_msg)

                # Print updated todo list at bottom after tool execution
                self._print_todo_list_at_bottom(plan)

                # Have agent review the plan and update todo list if needed
                if plan.todo:  # Only review if there are more steps
                    plan = await selected_agent.review_plan(plan, goal)

                # Save plan after each iteration
                self._save_plan_to_trace_dir(plan, iteration, goal)

                # Save trace after each iteration (overwrites same file for real-time updates)
                if self.traces_dir and session_id:
                    save_trace_file(session_id, self.traces_dir)

            # Check if we hit the iteration limit
            if iteration >= max_iterations:
                # Add error message to todo list
                from ..runtime.plan import Step
                error_step = Step(
                    tool_name="message",
                    parameters={
                        "message": f"Exceeded maximum iterations ({max_iterations}) while executing plan",
                        "category": "error"
                    },
                    description="Iteration limit exceeded"
                )
                plan.todo.append(error_step)

            # Clear any remaining todo list and print final completion status
            self._clear_todo_lines()
            self._print_completion_status(plan)

            return plan

        except Exception as e:
            # Save error trace if traces directory is configured
            if self.traces_dir and session_id:
                save_trace_file(f"{session_id}_error", self.traces_dir)

            print(f"\n❌ ORCHESTRATOR ERROR: {str(e)}")
            print("\n🚫 Task failed due to orchestrator error")

            error_plan = Plan.create_error_response(
                error=str(e),
                description=f"Orchestrator error processing: {goal[:50]}..."
            )
            return error_plan