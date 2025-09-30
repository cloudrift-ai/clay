"""Clay orchestrator that uses agents to create plans and to execute them."""

import asyncio
import json
import os
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ..llm import completion
from ..trace import clear_trace, save_trace_file, set_session_id, trace_operation
from .plan import Plan


class InteractiveConsole:
    """Simplified console display with a single print function that handles clearing."""

    def __init__(self):
        self.supports_ansi = self._check_ansi_support()
        self.tracked_lines = 0  # Lines that will be cleared on next display

    def _check_ansi_support(self) -> bool:
        """Check if terminal supports ANSI escape sequences."""
        return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty() and os.getenv('TERM') != 'dumb'

    def display(self, content: str = "", track_lines: bool = True) -> None:
        """Single print function that displays content and optionally tracks lines for clearing.

        Args:
            content: Content to display (can be multi-line string)
            track_lines: If True, clears previous tracked content and tracks this content
        """
        # Clear previously tracked lines if we're tracking new content
        if track_lines and self.supports_ansi and self.tracked_lines > 0:
            for _ in range(self.tracked_lines):
                sys.stdout.write('\033[A')  # Move cursor up one line
                sys.stdout.write('\033[K')  # Clear line
            sys.stdout.flush()
            self.tracked_lines = 0

        # Display the content
        if content:
            print(content)

            # Track lines for future clearing if requested
            if track_lines:
                self.tracked_lines = len(content.split('\n'))
        elif track_lines:
            # Reset tracking if displaying empty content
            self.tracked_lines = 0


@dataclass
class ToolOutputBuffer:
    """Buffer for capturing and summarizing tool output in real-time."""

    def __init__(self, tool_name: str, parameters: dict[str, Any]):
        self.tool_name = tool_name
        self.parameters = parameters
        self.start_time = time.time()
        self.end_time = None
        self.lines = []
        self.total_lines = 0
        self.max_display_lines = 12
        self._lock = threading.Lock()
        self.last_displayed_lines = 0  # Track how many lines were last displayed
        self.is_finished = False  # Track if tool execution is complete
        self.is_success = None  # Track success/failure state

    def add_output(self, text: str) -> None:
        """Add output text to the buffer."""
        if not text:
            return

        with self._lock:
            new_lines = text.splitlines()
            self.lines.extend(new_lines)
            self.total_lines += len(new_lines)

            # Keep only the last max_display_lines for real-time display
            if len(self.lines) > self.max_display_lines:
                self.lines = self.lines[-self.max_display_lines:]

    def finish(self, success: bool = True) -> None:
        """Mark the tool execution as finished.

        Args:
            success: Whether the tool execution was successful
        """
        with self._lock:
            self.end_time = time.time()
            self.is_finished = True
            self.is_success = success

    def get_execution_time(self) -> float:
        """Get execution time in seconds."""
        end_time = self.end_time if self.end_time else time.time()
        return end_time - self.start_time

    def get_real_time_summary(self, use_colors: bool = True) -> tuple[str, int]:
        """Get real-time summary showing last 20 lines, total count, and execution time.

        Args:
            use_colors: Whether to use ANSI color codes

        Returns:
            tuple[str, int]: (summary_text, lines_count_in_summary)
        """
        with self._lock:
            execution_time = self.get_execution_time()

            summary_parts = []

            # Determine status and colors
            if not self.is_finished:
                status = "Running"
                status_color = "\033[33m" if use_colors else ""  # Yellow for running
            elif self.is_success:
                status = "Success"
                status_color = "\033[32m" if use_colors else ""  # Green for success
            else:
                status = "Failed"
                status_color = "\033[31m" if use_colors else ""  # Red for failure

            reset_color = "\033[0m" if use_colors else ""
            gray_color = "\033[37m" if use_colors else ""  # Gray for output text

            # Header with tool info and stats
            summary_parts.append(
                f"  ⎿ {status_color}{status}{reset_color} "
                f"({self.total_lines} lines, {execution_time:.1f}s)"
            )

            # Show last lines (up to max_display_lines) in gray
            if self.lines:
                display_lines = self.lines[-self.max_display_lines:]
                for line in display_lines:
                    summary_parts.append(f"     {gray_color}{line}{reset_color}")

                # If there are more lines than displayed, show indicator
                if self.total_lines > len(self.lines):
                    hidden_lines = self.total_lines - len(self.lines)
                    summary_parts.append(
                        f"     {gray_color}... (+{hidden_lines} earlier lines){reset_color}"
                    )
                    lines_in_summary = len(summary_parts)
                else:
                    lines_in_summary = len(summary_parts)
            else:
                summary_parts.append(f"     {gray_color}(no output yet){reset_color}")
                lines_in_summary = len(summary_parts)

            return "\n".join(summary_parts), lines_in_summary

    def has_new_output(self) -> bool:
        """Check if there's new output since last display."""
        with self._lock:
            return self.total_lines > self.last_displayed_lines or self.is_finished

    def mark_displayed(self) -> None:
        """Mark current output as displayed."""
        with self._lock:
            self.last_displayed_lines = self.total_lines

    def get_final_summary(self, use_colors: bool = True) -> str:
        """Get final summary for completed tool execution.

        Args:
            use_colors: Whether to use ANSI color codes
        """
        with self._lock:
            execution_time = self.get_execution_time()

            # Determine colors based on success/failure
            if self.is_success:
                status = "Success"
                status_color = "\033[32m" if use_colors else ""  # Green
            else:
                status = "Failed"
                status_color = "\033[31m" if use_colors else ""  # Red

            reset_color = "\033[0m" if use_colors else ""
            gray_color = "\033[37m" if use_colors else ""  # Gray for output

            if self.total_lines == 0:
                return f"  ⎿ {status_color}{status}{reset_color} (no output, {execution_time:.1f}s)"
            elif self.total_lines <= self.max_display_lines:
                # Show all lines if not too many
                summary_parts = [
                    f"  ⎿ {status_color}{status}{reset_color} "
                    f"({self.total_lines} lines, {execution_time:.1f}s)"
                ]
                for line in self.lines:
                    summary_parts.append(f"     {gray_color}{line}{reset_color}")
                return "\n".join(summary_parts)
            else:
                # Show last 20 lines with summary
                summary_parts = [
                    f"  ⎿ {status_color}{status}{reset_color} "
                    f"({self.total_lines} lines, {execution_time:.1f}s)"
                ]
                if self.total_lines > self.max_display_lines:
                    hidden_count = self.total_lines - self.max_display_lines
                    summary_parts.append(
                        f"     {gray_color}... (+{hidden_count} earlier lines){reset_color}"
                    )
                for line in self.lines[-self.max_display_lines:]:
                    summary_parts.append(f"     {gray_color}{line}{reset_color}")
                return "\n".join(summary_parts)


class ClayOrchestrator:
    """Orchestrator that coordinates agents and plan execution."""

    def __init__(
        self,
        traces_dir: Optional[Path] = None,
        interactive: bool = False,
        disable_llm: bool = False,
    ):
        """Initialize the orchestrator with all available agents.

        Args:
            traces_dir: Directory to save traces and plan files. If None, uses _trace/
            interactive: Enable interactive mode with user input prompts during execution
            disable_llm: Disable LLM calls for testing (skips agent selection and plan review)
        """
        from ..agents.coding_agent import CodingAgent
        from ..agents.llm_agent import LLMAgent

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

        # Real-time output tracking
        self._current_tool_buffer = None
        self._output_lock = threading.Lock()

        # Interactive console for display management
        self.console = InteractiveConsole()

    @trace_operation
    async def select_agent(self, goal: str) -> str:
        """Use LLM to select the best agent for the task."""
        agent_descriptions = self._build_agent_descriptions()
        available_agent_names = list(self.agents.keys())

        available_agents_str = ', '.join(available_agent_names)
        system_prompt = f"""You are an agent router that selects the best agent for a given task.

Available agents:
{agent_descriptions}

Choose the most appropriate agent for the task.
Respond with ONLY the agent name from: {available_agents_str}.

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

    def _get_tool_display_name(self, tool_name: str, parameters: dict[str, Any]) -> str:
        """Get formatted tool display name."""
        if tool_name == "bash":
            command = parameters.get('command', '')
            if len(command) > 60:
                command = command[:57] + "..."
            return f"Bash({command})"
        elif tool_name == "write":
            file_path = parameters.get('file_path', '')
            return f"Write({file_path})"
        elif tool_name == "read":
            file_path = parameters.get('file_path', '')
            return f"Read({file_path})"
        else:
            return f"{tool_name.title()}(...)"

    def create_plan_from_goal(self, goal: str) -> Plan:
        """Create an initial plan from a goal with a UserMessageTool step.

        Args:
            goal: The user's task description

        Returns:
            Plan with a completed UserMessageTool step containing the goal
        """
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
        return Plan(todo=[], completed=[user_message_step])

    def _get_plan_summary_content(self, plan: Plan, interactive: bool = False) -> str:
        """Get plan summary content as a string for display."""
        if not plan.todo:
            content = "📋 ✅ All tasks completed!"
        else:
            lines = []
            lines.append("")  # Separator

            current_task = plan.todo[0].description
            lines.append(f"📋 [{len(plan.todo)} remaining] Current: {current_task}")

            # Show up to 10 upcoming tasks (including current)
            max_tasks_to_show = 10
            tasks_to_show = min(len(plan.todo), max_tasks_to_show)

            for i in range(1, tasks_to_show):
                if i < len(plan.todo):
                    task = plan.todo[i].description
                    lines.append(f"   {i}. {task}")

            # Add truncation notice if more than max_tasks_to_show items
            if len(plan.todo) > max_tasks_to_show:
                remaining = len(plan.todo) - max_tasks_to_show
                lines.append(f"   ... (+{remaining} more tasks)")

            # Add prompt in interactive mode
            if interactive and plan.todo:
                lines.append("")
                lines.append("❯ Waiting for next action...")

            content = "\n".join(lines)

        return content

    def _get_tool_output_content(self, buffer: 'ToolOutputBuffer', blink_state: bool = True) -> str:
        """Get tool output content as a string for display."""
        lines = []

        # Tool header with blinking indicator (only blink if ANSI supported)
        tool_display = self._get_tool_display_name(buffer.tool_name, buffer.parameters)

        if self.console.supports_ansi:
            yellow = "\033[33m"
            reset = "\033[0m"
            if blink_state:
                lines.append(f"{yellow}⏺{reset} {tool_display}")
            else:
                lines.append(f"  {tool_display}")
        else:
            # No blinking without ANSI support
            lines.append(f"⏺ {tool_display}")

        # Tool output with timer
        summary, _ = buffer.get_real_time_summary(use_colors=self.console.supports_ansi)
        lines.append(summary)

        return "\n".join(lines)

    def _print_tool_execution_summary(
        self, tool: Any, tool_name: str, parameters: dict[str, Any], result, buffer
    ) -> None:
        """Print console-friendly summary of tool execution in Claude Code format."""
        # Get the tool's formatted display with colored indicator
        tool_display = tool.get_tool_call_display(parameters)

        # Add colored indicator based on success/failure
        if self.console.supports_ansi:
            if buffer.is_success:
                # Green checkmark for success
                indicator = "\033[32m✓\033[0m"
            else:
                # Red X for failure
                indicator = "\033[31m✗\033[0m"
            # Replace the default indicator with colored one
            if tool_display.startswith("⏺"):
                tool_display = indicator + tool_display[1:]

        print(tool_display)

        # Print the buffered summary with colors
        summary = buffer.get_final_summary(use_colors=self.console.supports_ansi)
        if summary:
            print(summary)
            print()  # Add empty line after tool step display


    def _print_completion_status(self, plan: Plan) -> None:
        """Print final completion status."""
        if not plan.todo:
            success_msg = f"\n🎉 SUCCESS: All {len(plan.completed)} tasks completed!"
            self.console.display(success_msg, track_lines=False)
        else:
            incomplete_msg = (
                f"\n⚠️  INCOMPLETE: {len(plan.completed)} completed, "
                f"{len(plan.todo)} remaining"
            )
            self.console.display(incomplete_msg, track_lines=False)


    async def _monitor_tool_output(self, buffer: ToolOutputBuffer) -> None:
        """Monitor tool output buffer and display real-time updates for tool execution only."""
        iteration = 0

        while not buffer.is_finished:
            try:
                await asyncio.sleep(0.5)  # Check every 500ms
                iteration += 1
                blink_state = iteration % 2 == 0  # Toggle every iteration

                # Only update display if:
                # 1. We support ANSI (for in-place updates)
                # 2. OR there's new output to show
                if self.console.supports_ansi or buffer.has_new_output():
                    # Get tool output content and display with tracking
                    tool_content = self._get_tool_output_content(buffer, blink_state)
                    self.console.display(tool_content)
                    buffer.mark_displayed()

            except asyncio.CancelledError:
                # Clear display when cancelled by displaying empty content
                self.console.display("", track_lines=True)
                break
            except Exception:
                # Ignore errors to avoid breaking tool execution
                pass

    @trace_operation
    async def process_task(self, plan: 'Plan', session_id: str = "clay_session") -> 'Plan':
        """Process a task using iterative agent planning and execution.

        Args:
            plan: Plan to execute. Create using create_plan_from_goal() if starting from a goal.
            session_id: Session identifier for tracing (default: "clay_session")

        The process:
        1. Execute next step from todo list
        2. Agent reviews plan with completed step and updates todo list (unless disabled)
        3. Repeat until todo list is empty
        """

        iteration = 0
        while plan.todo:
            self._save_plan_to_trace_dir(plan, iteration)
            plan = await self._execute_next_step(plan, self.agent_tools['coding_agent'], 'coding_agent', iteration, session_id)
            iteration += 1

        # Print final completion status
        self._print_completion_status(plan)

        return plan

    async def process_task_interactive(self, plan: Plan, session_id: str = "clay_session") -> None:
        """Run Clay in interactive REPL mode with prompt_toolkit.

        Args:
            session_id: Session identifier for tracing (default: "clay_session")

        This method executes the plan continuously without blocking. It allows user input
        to augment the plan at any time by adding user_message steps to the completed list.
        """
        from prompt_toolkit import PromptSession
        from prompt_toolkit.patch_stdout import patch_stdout
        from clay.orchestrator.plan import Step

        session = PromptSession("❯ ")
        iteration = 0
        user_input_queue = asyncio.Queue()
        should_exit = False

        async def input_handler():
            """Background task to handle user input without blocking execution."""
            nonlocal should_exit
            while not should_exit:
                try:
                    line = await session.prompt_async()
                    await user_input_queue.put(line.strip())
                except (KeyboardInterrupt, EOFError):
                    should_exit = True
                    break

        # Start input handler in background
        with patch_stdout(raw=True):
            input_task = asyncio.create_task(input_handler())

            try:
                while not should_exit:
                    # Check for user input without blocking
                    user_input = None
                    if len(plan.todo) == 0:
                        user_input = await user_input_queue.get()
                    else:
                        try:
                            user_input = user_input_queue.get_nowait()
                        except asyncio.QueueEmpty:
                            pass

                    # Process user input if available
                    if user_input:
                        if user_input.lower() in ['exit', 'quit', 'q']:
                            print("Goodbye! 👋")
                            should_exit = True
                            break

                        if user_input:
                            print()  # Add spacing before task execution

                            # Add user input as a completed user_message step
                            user_message_step = Step(
                                tool_name="user_message",
                                parameters={"message": user_input},
                                description="User input"
                            )
                            user_message_step.status = "SUCCESS"
                            user_message_step.result = {
                                "output": user_input,
                                "metadata": {
                                    "message": user_input,
                                    "tool_type": "user_context",
                                    "timestamp": datetime.now().isoformat()
                                }
                            }

                            # Add user message to existing plan's completed steps
                            plan.completed.append(user_message_step)

                    # Execute plan steps if there are any
                    plan = await self._execute_next_step(
                        plan,
                        self.agent_tools['coding_agent'],
                        'coding_agent',
                        iteration,
                        session_id
                    )
                    iteration += 1

            finally:
                # Clean up input handler
                should_exit = True
                input_task.cancel()
                try:
                    await input_task
                except asyncio.CancelledError:
                    pass

    async def _execute_next_step(
        self, plan: Plan, agent_tools: dict, selected_agent, iteration: int, session_id: str
    ) -> Plan:
        """Execute the next step in the plan and return updated plan."""

        # Have agent review the plan and update todo list if needed (unless LLM is disabled)
        # Review if there are remaining todos OR if there are any failures to address
        plan = await self.agents[selected_agent].review_plan(plan)

        # Save plan at each iteration
        self._save_plan_to_trace_dir(plan, iteration)
        save_trace_file(session_id, self.traces_dir)

        if len(plan.todo) == 0:
            return plan

        # Execute the next step
        next_step = plan.todo[0]
        tool_name = next_step.tool_name
        parameters = next_step.parameters

        tool = agent_tools[tool_name]
        monitor_task = None  # Initialize for proper cleanup

        # Create output buffer for this tool execution
        buffer = ToolOutputBuffer(tool_name, parameters)
        self._current_tool_buffer = buffer

        # Start real-time output monitoring task
        monitor_task = asyncio.create_task(self._monitor_tool_output(buffer))

        # Create callback for real-time output
        # (bash tool will use it, others will ignore it)
        def output_callback(line: str, buffer=buffer):
            buffer.add_output(line)

        # Execute the tool with potential streaming support
        result = await tool.run(
            output_callback=output_callback,
            **parameters
        )

        # For tools that don't support streaming, capture output from result
        if tool_name != "bash":
            tool_output = ""
            if hasattr(result, 'stdout') and result.stdout:
                tool_output = result.stdout
            elif hasattr(result, 'output') and result.output:
                tool_output = result.output

            # Add output to buffer
            if tool_output:
                buffer.add_output(tool_output)

        buffer.finish(success=True)

        # Cancel monitoring task and wait for it to complete
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        # Show final buffered summary
        self._print_tool_execution_summary(
            tool, tool_name, parameters, result, buffer
        )

        # Move step to completed with successful result
        plan.complete_next_step(result=result.to_dict())
        self._current_tool_buffer = None

        # Display plan summary after tool execution
        plan_content = self._get_plan_summary_content(plan, self.interactive)
        self.console.display(plan_content)

        return plan
