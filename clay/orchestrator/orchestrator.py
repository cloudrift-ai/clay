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
    """Manages interactive console display with proper state tracking for clearing output."""

    def __init__(self):
        self.supports_ansi = self._check_ansi_support()
        self.current_display_lines = 0
        self._plan_displayed = False

    def _check_ansi_support(self) -> bool:
        """Check if terminal supports ANSI escape sequences."""
        return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty() and os.getenv('TERM') != 'dumb'

    def clear_current_display(self) -> None:
        """Clear the currently displayed content if ANSI is supported."""
        if self.supports_ansi and self.current_display_lines > 0:
            for _ in range(self.current_display_lines):
                sys.stdout.write('\033[A')  # Move cursor up one line
                sys.stdout.write('\033[K')  # Clear line
            sys.stdout.flush()
            self.current_display_lines = 0

    def display_lines(self, lines: list[str], track_for_clearing: bool = True) -> None:
        """Display lines and optionally track them for clearing."""
        if track_for_clearing:
            self.clear_current_display()

        for line in lines:
            print(line)

        if track_for_clearing:
            self.current_display_lines = len(lines)

    def display_plan_summary(self, plan: Plan, interactive: bool = False) -> None:
        """Display plan summary and prompt, but only once per tool cycle."""
        if not plan.todo or self._plan_displayed:
            return

        lines = []
        lines.append("")  # Separator

        # Add plan summary
        if not plan.todo:
            lines.append("📋 ✅ All tasks completed!")
        else:
            current_task = plan.todo[0].description
            lines.append(f"📋 [{len(plan.todo)} remaining] Current: {current_task}")

            if len(plan.todo) > 1:
                next_task = plan.todo[1].description
                lines.append(f"   Next: {next_task}")

            if len(plan.todo) > 2:
                lines.append(f"   +{len(plan.todo) - 2} more tasks...")

        # Add prompt in interactive mode
        if interactive and plan.todo:
            lines.append("")
            lines.append("❯ Waiting for next action...")

        self.display_lines(lines, track_for_clearing=True)
        self._plan_displayed = True

    def on_tool_started(self) -> None:
        """Called when a tool starts executing - clears plan and resets state."""
        self.clear_current_display()
        self._plan_displayed = False

    def on_tool_finished(self) -> None:
        """Called when a tool finishes executing - plan can be shown again."""
        self._plan_displayed = False

    def display_tool_output(self, buffer: 'ToolOutputBuffer', blink_state: bool = True, get_tool_display_name_func=None) -> None:
        """Display tool output with blinking indicator and real-time updates."""
        display_lines = []

        # Tool header with blinking indicator (only blink if ANSI supported)
        if get_tool_display_name_func:
            tool_display = get_tool_display_name_func(buffer.tool_name, buffer.parameters)
        else:
            tool_display = f"{buffer.tool_name.title()}(...)"

        if self.supports_ansi:
            yellow = "\033[33m"
            reset = "\033[0m"
            if blink_state:
                display_lines.append(f"{yellow}⏺{reset} {tool_display}")
            else:
                display_lines.append(f"  {tool_display}")
        else:
            # No blinking without ANSI support
            display_lines.append(f"⏺ {tool_display}")

        # Tool output with timer
        summary, _ = buffer.get_real_time_summary(use_colors=self.supports_ansi)
        summary_lines = summary.split('\n')
        display_lines.extend(summary_lines)

        # Display with tracking for clearing
        self.display_lines(display_lines, track_for_clearing=True)


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
                summary_parts = [f"  ⎿ {status_color}{status}{reset_color} ({self.total_lines} lines, {execution_time:.1f}s)"]
                for line in self.lines:
                    summary_parts.append(f"     {gray_color}{line}{reset_color}")
                return "\n".join(summary_parts)
            else:
                # Show last 20 lines with summary
                summary_parts = [f"  ⎿ {status_color}{status}{reset_color} ({self.total_lines} lines, {execution_time:.1f}s)"]
                if self.total_lines > self.max_display_lines:
                    summary_parts.append(f"     {gray_color}... (+{self.total_lines - self.max_display_lines} earlier lines){reset_color}")
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

Choose the most appropriate agent for the task. Respond with ONLY the agent name from: {available_agents_str}.

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

    def _get_plan_summary(self, plan: Plan) -> list[str]:
        """Get compact plan summary lines for display."""
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

        return lines

    def _print_tool_execution_summary(self, tool: Any, tool_name: str, parameters: dict[str, Any], result, buffer: ToolOutputBuffer) -> None:
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


    def _print_completion_status(self, plan: Plan) -> None:
        """Print final completion status."""
        if not plan.todo:
            print(f"\n🎉 SUCCESS: All {len(plan.completed)} tasks completed!")
        else:
            print(f"\n⚠️  INCOMPLETE: {len(plan.completed)} completed, {len(plan.todo)} remaining")


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
                    # Use console method to display tool output with blinking
                    self.console.display_tool_output(
                        buffer,
                        blink_state=blink_state,
                        get_tool_display_name_func=self._get_tool_display_name
                    )
                    buffer.mark_displayed()

            except asyncio.CancelledError:
                # Clear display when cancelled
                self.console.clear_current_display()
                break
            except Exception:
                # Ignore errors to avoid breaking tool execution
                pass

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

        # Initialize session_id for error handling
        session_id = "clay_session"

        try:
            # Set up tracing with single session
            clear_trace()
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
            iteration = 0
            self._save_plan_to_trace_dir(plan, 0)

            # Display initial plan summary
            self.console.display_plan_summary(plan, self.interactive)

            while plan.todo:
                iteration += 1

                # Execute the next step
                next_step = plan.todo[0]
                tool_name = next_step.tool_name
                parameters = next_step.parameters

                if tool_name in agent_tools:
                    tool = agent_tools[tool_name]
                    monitor_task = None  # Initialize for proper cleanup
                    try:
                        # Notify console that tool is starting
                        self.console.on_tool_started()

                        # Create output buffer for this tool execution
                        buffer = ToolOutputBuffer(tool_name, parameters)
                        self._current_tool_buffer = buffer

                        # Start real-time output monitoring task
                        monitor_task = asyncio.create_task(self._monitor_tool_output(buffer))

                        try:
                            # Create callback for real-time output (bash tool will use it, others will ignore it)
                            def output_callback(line: str):
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
                            self._print_tool_execution_summary(tool, tool_name, parameters, result, buffer)

                            # Move step to completed with successful result
                            plan.complete_next_step(result=result.to_dict())
                            self._current_tool_buffer = None

                            # Notify console that tool finished
                            self.console.on_tool_finished()

                        except Exception as tool_error:
                            # Cancel monitoring task
                            monitor_task.cancel()
                            try:
                                await monitor_task
                            except asyncio.CancelledError:
                                pass
                            raise tool_error

                    except Exception as e:
                        # Tool execution failed - mark as FAILURE
                        error_msg = str(e)

                        # Mark buffer as failed if it exists
                        if self._current_tool_buffer:
                            self._current_tool_buffer.finish(success=False)

                            # Cancel monitoring task if it's running
                            if monitor_task:
                                monitor_task.cancel()
                                try:
                                    await monitor_task
                                except asyncio.CancelledError:
                                    pass

                            # Show final summary with failure status
                            self._print_tool_execution_summary(tool, tool_name, parameters, None, self._current_tool_buffer)
                            self._current_tool_buffer = None
                        else:
                            # Fallback if no buffer
                            print(f"\n❌ Tool execution failed: {error_msg}")

                        plan.complete_next_step(error=error_msg)

                        # Notify console that tool finished (even with error)
                        self.console.on_tool_finished()
                else:
                    error_msg = f"Tool {tool_name} not found"
                    print(f"\n❌ Tool execution failed: {error_msg}")
                    plan.complete_next_step(error=error_msg)

                # Display plan summary after tool execution (only if not already shown)
                self.console.display_plan_summary(plan, self.interactive)

                # Have agent review the plan and update todo list if needed (unless LLM is disabled)
                # Review if there are remaining todos OR if there are any failures to address
                should_review = bool(plan.todo) or plan.has_failed
                if should_review and not self.disable_llm:
                    plan = await selected_agent.review_plan(plan)

                # Save plan after each iteration
                self._save_plan_to_trace_dir(plan, iteration)

                # Save trace after each iteration (overwrites same file)
                save_trace_file(session_id, self.traces_dir)

            # Print final completion status
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