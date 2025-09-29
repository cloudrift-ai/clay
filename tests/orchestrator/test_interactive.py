"""Tests for interactive orchestrator execution and output summarization."""

import pytest
import tempfile
import io
import sys
from pathlib import Path

from clay.orchestrator.orchestrator import ClayOrchestrator
from clay.orchestrator.plan import Plan, Step


class TestInteractiveExecution:
    """Test interactive orchestrator execution and output behavior."""

    @pytest.mark.asyncio
    async def test_plan_execution_with_output_summarization(self):
        """Test that plans execute correctly and output is properly summarized."""
        # Create a plan with multiple steps that will generate output
        steps = [
            Step(
                tool_name="write",
                parameters={"file_path": "test.txt", "content": "Hello World"},
                description="Create test file"
            ),
            Step(
                tool_name="bash",
                parameters={"command": "cat test.txt"},
                description="Read test file"
            )
        ]

        plan = Plan(todo=steps)

        # Create orchestrator with LLM disabled
        orchestrator = ClayOrchestrator(disable_llm=True)

        # Capture stdout to verify output behavior
        captured_output = io.StringIO()

        with io.StringIO() as captured_output:
            original_stdout = sys.stdout
            sys.stdout = captured_output

            try:
                # Execute the plan directly
                result_plan = await orchestrator.process_task(plan=plan)

                # Verify plan executed successfully
                assert result_plan.is_complete
                assert not result_plan.has_failed
                # Check that our steps were completed (may include additional user_message steps)
                assert len(result_plan.completed) >= len(steps)

            finally:
                sys.stdout = original_stdout

            # Get the captured output
            output_content = captured_output.getvalue()

            # Should contain tool execution summaries (updated for buffered output)
            assert "⏺ Write(test.txt)" in output_content or "test.txt" in output_content or "Success" in output_content

    @pytest.mark.asyncio
    async def test_plan_execution_without_llm(self):
        """Test complete plan execution without any LLM calls."""
        # Create a simple plan with a bash command
        steps = [
            Step(
                tool_name="bash",
                parameters={"command": "echo 'Hello from test'"},
                description="Echo test message"
            )
        ]

        plan = Plan(todo=steps)

        # Create orchestrator with LLM disabled
        orchestrator = ClayOrchestrator(disable_llm=True)

        # Execute the plan
        result_plan = await orchestrator.process_task(plan=plan)

        # Verify plan executed successfully
        assert result_plan.is_complete
        assert not result_plan.has_failed
        # Check that our steps were completed (may include additional user_message steps)
        assert len(result_plan.completed) >= len(steps)

        # Verify the bash step was executed correctly
        bash_steps = [step for step in result_plan.completed if step.tool_name == "bash"]
        assert len(bash_steps) >= 1
        bash_step = bash_steps[0]
        assert bash_step.status == "SUCCESS"
        assert bash_step.result is not None

    @pytest.mark.asyncio
    async def test_plan_execution_with_multiple_steps(self):
        """Test plan execution with multiple steps in sequence."""
        # Create a plan with multiple steps
        steps = [
            Step(
                tool_name="write",
                parameters={"file_path": "greeting.txt", "content": "Hello World"},
                description="Create greeting file"
            ),
            Step(
                tool_name="bash",
                parameters={"command": "wc -w greeting.txt"},
                description="Count words in greeting file"
            ),
            Step(
                tool_name="bash",
                parameters={"command": "rm greeting.txt"},
                description="Clean up greeting file"
            )
        ]

        plan = Plan(todo=steps)

        # Create orchestrator with LLM disabled
        orchestrator = ClayOrchestrator(disable_llm=True)

        # Execute the plan
        result_plan = await orchestrator.process_task(plan=plan)

        # Verify all steps executed successfully
        assert result_plan.is_complete
        assert not result_plan.has_failed
        # Check that our steps were completed (may include additional user_message steps)
        assert len(result_plan.completed) >= len(steps)

        # Verify each step completed successfully
        for step in result_plan.completed:
            assert step.status == "SUCCESS"
            assert step.result is not None

    def test_orchestrator_initialization_with_disable_llm(self):
        """Test that orchestrator properly initializes with LLM disabled."""
        # Test with LLM disabled
        orchestrator = ClayOrchestrator(disable_llm=True)

        # Should have disable_llm flag set
        assert orchestrator.disable_llm is True

        # Should always use _trace directory
        assert orchestrator.traces_dir == Path("_trace")
        assert orchestrator.traces_dir.exists()

        # Should have agents initialized
        assert 'coding_agent' in orchestrator.agents
        assert 'llm_agent' in orchestrator.agents

        # Test ANSI support detection
        assert hasattr(orchestrator, '_supports_ansi')
        assert isinstance(orchestrator._supports_ansi, bool)

    @pytest.mark.asyncio
    async def test_output_summarization_behavior(self):
        """Test that output summarization works correctly."""
        # Create a plan with a command that produces output
        steps = [
            Step(
                tool_name="bash",
                parameters={"command": "ls -la"},
                description="List directory contents"
            )
        ]

        plan = Plan(todo=steps)

        # Create orchestrator with LLM disabled
        orchestrator = ClayOrchestrator(disable_llm=True)

        # Capture stdout to verify output behavior
        original_stdout = sys.stdout
        captured_output = io.StringIO()

        try:
            sys.stdout = captured_output

            # Execute the plan
            result_plan = await orchestrator.process_task(plan=plan)

            # Verify plan executed successfully
            assert result_plan.is_complete
            assert not result_plan.has_failed

        finally:
            sys.stdout = original_stdout

        # Get the captured output
        output_content = captured_output.getvalue()

        # Should contain the plan execution output (todo list, completion status, etc.)
        assert "PLANNED TASKS" in output_content or "SUCCESS" in output_content or "completed" in output_content

    @pytest.mark.asyncio
    async def test_plan_execution_with_user_input_tool(self):
        """Test that plans with UserInputTool block until input is provided on stdin."""
        # Create a plan with UserInputTool that requires interactive input
        steps = [
            Step(
                tool_name="user_input",
                parameters={
                    "prompt": "What is your favorite color?",
                    "context": "We need this information to proceed"
                },
                description="Get user's favorite color"
            ),
            Step(
                tool_name="message",
                parameters={
                    "message": "Thank you for your input!",
                    "category": "info"
                },
                description="Acknowledge user input"
            )
        ]

        plan = Plan(todo=steps)

        # Create orchestrator with LLM disabled and interactive mode enabled
        orchestrator = ClayOrchestrator(disable_llm=True, interactive=True)

        # Capture stdout to verify prompt appears
        captured_output = io.StringIO()
        original_stdout = sys.stdout
        original_stdin = sys.stdin

        # Create a mock stdin that will provide input
        mock_input = io.StringIO("blue\n")

        try:
            sys.stdout = captured_output
            # Redirect stdin to our mock input
            sys.stdin = mock_input

            # Execute the plan - this should block at the user_input step
            result_plan = await orchestrator.process_task(plan=plan)

            # Verify plan executed successfully
            assert result_plan.is_complete
            assert not result_plan.has_failed

            # Check that both steps were completed
            assert len(result_plan.completed) >= 2

            # Verify the user input step was executed and captured input
            user_input_steps = [step for step in result_plan.completed if step.tool_name == "user_input"]
            assert len(user_input_steps) >= 1

            user_input_step = user_input_steps[0]
            assert user_input_step.status == "SUCCESS"
            assert user_input_step.result is not None
            assert user_input_step.result.get("output") == "blue"

            # Verify the message step was executed
            message_steps = [step for step in result_plan.completed if step.tool_name == "message"]
            assert len(message_steps) >= 1

            message_step = message_steps[0]
            assert message_step.status == "SUCCESS"
            assert message_step.result is not None

        finally:
            sys.stdout = original_stdout
            sys.stdin = original_stdin

        # Get the captured output (after restoring stdout)
        output_content = captured_output.getvalue()

        # Should contain the user input prompt
        assert "What is your favorite color?" in output_content
        assert "We need this information to proceed" in output_content

    @pytest.mark.asyncio
    async def test_user_input_tool_not_available_when_non_interactive(self):
        """Test that UserInputTool is not available when interactive=False."""
        # Create a plan with UserInputTool
        steps = [
            Step(
                tool_name="user_input",
                parameters={
                    "prompt": "This should fail",
                    "context": "Testing non-interactive mode"
                },
                description="This should fail"
            )
        ]

        plan = Plan(todo=steps)

        # Create orchestrator with LLM disabled and interactive mode disabled
        orchestrator = ClayOrchestrator(disable_llm=True, interactive=False)

        # Execute the plan - this should fail because UserInputTool is not registered
        result_plan = await orchestrator.process_task(plan=plan)

        # Verify plan failed due to missing tool
        assert result_plan.is_complete  # Plan still completes, but with failures
        assert result_plan.has_failed   # Plan should have failed

        # Verify the user input step failed with tool not found error
        user_input_steps = [step for step in result_plan.completed if step.tool_name == "user_input"]
        assert len(user_input_steps) >= 1

        user_input_step = user_input_steps[0]
        assert user_input_step.status == "FAILURE"
        assert user_input_step.error_message is not None
        assert "not found" in user_input_step.error_message.lower()

    @pytest.mark.asyncio
    async def test_long_output_command_with_output_replacement(self):
        """Test that long-running commands show full output during execution, then replace with summary."""
        # Create a plan with a command that produces long output
        steps = [
            Step(
                tool_name="bash",
                parameters={
                    "command": "python -c \"import time; [print(f'Line {i}: This is a test line with some content to make it longer') or time.sleep(0.01) for i in range(1, 21)]\""
                },
                description="Generate long output with multiple lines"
            ),
            Step(
                tool_name="bash",
                parameters={
                    "command": "echo 'Final command completed'"
                },
                description="Simple final command"
            )
        ]

        plan = Plan(todo=steps)

        # Create orchestrator with LLM disabled
        orchestrator = ClayOrchestrator(disable_llm=True)

        # Capture all stdout to analyze output behavior
        import threading

        captured_outputs = []
        output_lock = threading.Lock()

        class OutputCapture:
            def __init__(self, orig_stdout):
                self.orig_stdout = orig_stdout
                self.buffer = ""

            def write(self, text):
                with output_lock:
                    self.buffer += text
                    captured_outputs.append(text)
                # Also write to original stdout so we can see what's happening
                self.orig_stdout.write(text)

            def flush(self):
                self.orig_stdout.flush()

        original_stdout = sys.stdout
        output_capture = OutputCapture(original_stdout)

        try:
            sys.stdout = output_capture

            # Execute the plan
            result_plan = await orchestrator.process_task(plan=plan)

            # Verify plan executed successfully
            assert result_plan.is_complete
            assert not result_plan.has_failed

            # Check that both bash steps were completed
            bash_steps = [step for step in result_plan.completed if step.tool_name == "bash"]
            assert len(bash_steps) >= 2

            # Verify the first bash step (long output) was executed
            first_bash_step = bash_steps[0]
            assert first_bash_step.status == "SUCCESS"
            assert first_bash_step.result is not None

        finally:
            sys.stdout = original_stdout

        # Analyze the captured output (after restoring stdout)
        full_output = output_capture.buffer

        # Should contain the command output during execution (may be in last 20 lines due to new truncation)
        # Check for some lines that should be visible
        assert "Line 9: This is a test line" in full_output or "Line 10: This is a test line" in full_output
        assert "Line 20: This is a test line" in full_output

        # Should contain the tool execution summary format
        assert "⏺ Bash(" in full_output

        # Should contain plan progress indicators
        assert "PLANNED TASKS" in full_output or "remaining" in full_output

        # Should show completion status
        assert "SUCCESS" in full_output or "completed" in full_output

        # Should show output summary with line count and timing (the orchestrator's new summarization behavior)
        assert ("lines" in full_output and "s)" in full_output) or "… +" in full_output, "Should show output summary with timing and line count"

        # Verify that we see the detailed output lines in the captured output
        lines = full_output.split('\n')

        # Count how many "Line X:" entries we can see
        line_entries = [line for line in lines if "Line " in line and ": This is a test line" in line]
        assert len(line_entries) >= 5, f"Should show multiple lines of output, got {len(line_entries)}"

        # Verify the final command also executed
        assert "Final command completed" in full_output

        # Verify both commands show in the tool execution format
        bash_tool_calls = [line for line in lines if "⏺ Bash(" in line]
        assert len(bash_tool_calls) >= 2, "Should show both bash commands in summary format"