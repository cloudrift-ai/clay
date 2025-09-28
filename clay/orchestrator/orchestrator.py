"""Clay orchestrator that uses agents to create plans and to execute them."""

from pathlib import Path
from typing import Dict, Any, Optional
import json
import sys
import os
from datetime import datetime

from .plan import Plan
from ..llm import completion
from ..trace import trace_operation, clear_trace, save_trace_file, set_session_id


class ClayOrchestrator:
    """Orchestrator that coordinates agents and plan execution."""

    def __init__(self, traces_dir: Optional[Path] = None, interactive: bool = False, disable_llm: bool = False):
        """Initialize the orchestrator with all available agents.

        Args:
            traces_dir: Directory to save traces and plan files. If None, uses _trace/
            interactive: Enable interactive mode with user input prompts during execution
            disable_llm: Disable LLM calls for testing (skips agent selection and plan review)
        """
        from ..agents.llm_agent import LLMAgent
        from ..agents.coding_agent import CodingAgent

        # Set configuration first - always use _trace directory
        self.traces_dir = Path("_trace")
        self.traces_dir.mkdir(exist_ok=True)
        self.interactive = interactive
        self.disable_llm = disable_llm

        # Initialize all available agents
        self.agents = {
            'llm_agent': LLMAgent(),
            'coding_agent': CodingAgent()
        }

        # Create tool registries for each agent
        self.agent_tools = {}
        for agent_name, agent in self.agents.items():
            self.agent_tools[agent_name] = agent.tools if hasattr(agent, 'tools') else {}

            # Add UserInputTool to agents if in interactive mode
            if self.interactive and hasattr(agent, 'register_tool'):
                from ..tools import UserInputTool
                agent.register_tool(UserInputTool())
                # Update the tool registry to include the newly registered tool
                self.agent_tools[agent_name] = agent.tools

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

    def _save_plan_to_trace_dir(self, plan: Plan, iteration: int) -> Path:
        """Save the plan to the traces directory for debugging."""
        # Always use _trace directory
        trace_dir = self.traces_dir
        trace_dir.mkdir(parents=True, exist_ok=True)

        # Use simple filename that overwrites previous iterations
        filename = f"plan_iter_{iteration:03d}.json"
        filepath = trace_dir / filename

        # Create plan data with optimized structure for KV-cache
        # Goal is now embedded in UserMessageTool, no need for separate goal field
        plan_data = plan.to_dict()

        # Save to file (overwrites existing)
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

    async def _run_repl_mode(self) -> Plan:
        """Run Clay in interactive REPL mode."""
        try:
            while True:
                try:
                    print()
                    task = input("❯ ").strip()

                    if task.lower() in ['exit', 'quit', 'q']:
                        print("Goodbye! 👋")
                        break

                    if not task:
                        continue

                    print()  # Add spacing before task execution
                    # Execute the task using the normal process_task flow
                    await self.process_task(task)

                except KeyboardInterrupt:
                    print("\nGoodbye! 👋")
                    break
                except EOFError:
                    print("\nGoodbye! 👋")
                    break

        except Exception as e:
            print(f"❌ Error in interactive mode: {e}")

        # Return a simple completion plan for REPL mode
        from clay.orchestrator.plan import Plan
        return Plan(todo=[], completed=[])


    def _clear_todo_lines(self) -> None:
        """Clear the previously printed todo list lines."""
        if self._supports_ansi and self._todo_lines_count > 0:
            # Move cursor up and clear lines
            for _ in range(self._todo_lines_count):
                sys.stdout.write('\033[A')  # Move cursor up one line
                sys.stdout.write('\033[K')  # Clear line
            sys.stdout.flush()
            self._todo_lines_count = 0

    def _clear_tool_output_if_needed(self, lines_count: int) -> None:
        """Clear tool output lines if ANSI is supported."""
        if self._supports_ansi and lines_count > 0:
            for _ in range(lines_count):
                sys.stdout.write('\033[A')  # Move cursor up one line
                sys.stdout.write('\033[K')  # Clear line
            sys.stdout.flush()

    def _print_tool_execution_summary(self, tool: Any, tool_name: str, parameters: Dict[str, Any], result) -> None:
        """Print console-friendly summary of tool execution in Claude Code format."""
        # Get the tool's formatted display
        tool_call = tool.get_tool_call_display(parameters)
        print(tool_call)

        # Print the result summary with proper formatting
        if hasattr(result, 'get_formatted_output'):
            output = result.get_formatted_output()
        else:
            # Default formatting for results without custom formatter
            output = result.output or "Success"

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
        print(f"📋 PLANNED TASKS ({len(plan.todo)} total):")

        for i, step in enumerate(plan.todo[:8], 1):  # Show first 8 tasks
            print(f"  {i}. {step.description}")

        if len(plan.todo) > 8:
            print(f"  ... and {len(plan.todo) - 8} more tasks")

    def _print_completion_status(self, plan: Plan) -> None:
        """Print final completion status."""
        if not plan.todo:
            print(f"\n🎉 SUCCESS: All {len(plan.completed)} tasks completed!")
        else:
            print(f"\n⚠️  INCOMPLETE: {len(plan.completed)} completed, {len(plan.todo)} remaining")

    @trace_operation
    async def process_task(self, goal: Optional[str] = None, plan: Optional['Plan'] = None) -> 'Plan':
        """Process a task using iterative agent planning and execution.

        Args:
            goal: Task description. If None, starts interactive REPL mode.
            plan: Pre-built plan to execute. If provided, skips agent planning phase.

        The process:
        1. Agent creates initial plan (or use provided plan)
        2. Execute next step from todo list
        3. Agent reviews plan with completed step and updates todo list (unless disabled)
        4. Repeat until todo list is empty
        """

        # Handle REPL mode when no goal is provided
        if goal is None and plan is None:
            return await self._run_repl_mode()

        working_dir = Path.cwd()
        if not working_dir.exists():
            return Plan.create_error_response(
                error=f"Working directory {working_dir} does not exist",
                description="Working directory validation failed"
            )

        try:
            # Set up tracing with single session
            clear_trace()
            session_id = "clay_session"
            set_session_id(session_id)

            # Use provided plan or create initial plan with UserMessageTool
            if plan is None:
                from clay.orchestrator.plan import Step
                user_message_step = Step(
                    tool_name="user_message",
                    parameters={"message": goal},
                    description="User's initial request"
                )
                # Mark it as already completed since it represents the input
                user_message_step.status = "SUCCESS"
                user_message_step.result = {
                    "output": goal,
                    "metadata": {
                        "message": goal,
                        "tool_type": "user_context",
                        "timestamp": datetime.now().isoformat()
                    }
                }

                # Create initial plan with UserMessageTool
                plan = Plan(todo=[], completed=[user_message_step])

                if not self.disable_llm:
                    # Select the best agent for the task
                    selected_agent_name = await self.select_agent(goal)
                    selected_agent = self.agents[selected_agent_name]

                    # Get initial plan from agent (pass plan with UserMessageTool instead of goal)
                    plan = await selected_agent.run(plan)
                else:
                    # Default to coding agent when LLM is disabled
                    selected_agent_name = 'coding_agent'
                    selected_agent = self.agents[selected_agent_name]
            else:
                # Use provided plan, default to coding agent
                selected_agent_name = 'coding_agent'
                selected_agent = self.agents[selected_agent_name]

            agent_tools = self.agent_tools[selected_agent_name]

            # Save initial plan (iteration 0)
            self._save_plan_to_trace_dir(plan, 0)

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
                    try:
                        # Clear any existing todo list first
                        self._clear_todo_lines()

                        # Let tool execute and print freely
                        result = await tool.run(**parameters)

                        # Calculate lines that were printed (rough estimate from result output)
                        lines_printed = 0
                        if hasattr(result, 'stdout') and result.stdout:
                            # For tools that capture stdout (like bash), count those lines
                            lines_printed = len(result.stdout.splitlines())
                        elif hasattr(result, 'output') and result.output:
                            # For other tools, estimate from output
                            lines_printed = len(result.output.splitlines())

                        # Clear the tool's free-form output
                        self._clear_tool_output_if_needed(lines_printed)

                        # Replace with summary
                        self._print_tool_execution_summary(tool, tool_name, parameters, result)

                        # Move step to completed with successful result
                        plan.complete_next_step(result=result.to_dict())
                    except Exception as e:
                        # Tool execution failed - mark as FAILURE
                        error_msg = str(e)
                        print(f"\n❌ Tool execution failed: {error_msg}")
                        plan.complete_next_step(error=error_msg)
                else:
                    error_msg = f"Tool {tool_name} not found"
                    print(f"\n❌ Tool execution failed: {error_msg}")
                    plan.complete_next_step(error=error_msg)

                # Print updated todo list at bottom after tool execution
                self._print_todo_list_at_bottom(plan)

                # Have agent review the plan and update todo list if needed (unless LLM is disabled)
                # Review if there are remaining todos OR if there are any failures to address
                should_review = bool(plan.todo) or plan.has_failed
                if should_review and not self.disable_llm:
                    plan = await selected_agent.review_plan(plan)

                # Save plan after each iteration
                self._save_plan_to_trace_dir(plan, iteration)

                # Save trace after each iteration (overwrites same file)
                save_trace_file(session_id, self.traces_dir)

            # Check if we hit the iteration limit
            if iteration >= max_iterations:
                # Add error message to todo list
                from clay.orchestrator.plan import Step
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
            # Save error trace
            save_trace_file(f"{session_id}_error", self.traces_dir)

            print(f"\n❌ ORCHESTRATOR ERROR: {str(e)}")
            print("\n🚫 Task failed due to orchestrator error")

            # Get task description from goal or use generic fallback
            task_desc = goal[:50] if len(goal) <= 50 else f"{goal[:47]}..."
            error_plan = Plan.create_error_response(
                error=str(e),
                description=f"Orchestrator error processing: {task_desc}"
            )
            return error_plan