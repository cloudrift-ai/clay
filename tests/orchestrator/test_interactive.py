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
        # Import at test time to avoid circular imports
        from unittest.mock import AsyncMock

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

        # Mock the agent's review_plan to just return the plan unchanged when LLM disabled
        for agent in orchestrator.agents.values():
            agent.review_plan = AsyncMock(side_effect=lambda p: p)

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
                assert len([step for step in result_plan.completed if step.tool_name in ['write', 'bash']]) >= len(steps)

            finally:
                sys.stdout = original_stdout

            # Get the captured output
            output_content = captured_output.getvalue()

            # Should contain tool execution summaries (updated for buffered output)
            assert "⏺ Write(test.txt)" in output_content or "test.txt" in output_content or "Success" in output_content

    @pytest.mark.asyncio
    async def test_plan_execution_without_llm(self):
        """Test complete plan execution without any LLM calls."""
        # Import at test time to avoid circular imports
        from unittest.mock import AsyncMock

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

        # Mock the agent's review_plan to just return the plan unchanged when LLM disabled
        for agent in orchestrator.agents.values():
            agent.review_plan = AsyncMock(side_effect=lambda p: p)

        # Execute the plan
        result_plan = await orchestrator.process_task(plan=plan)

        # Verify plan executed successfully
        assert result_plan.is_complete
        assert not result_plan.has_failed
        # Check that our steps were completed (may include additional user_message steps)
        assert len([step for step in result_plan.completed if step.tool_name in ['write', 'bash']]) >= len(steps)

        # Verify the bash step was executed correctly
        bash_steps = [step for step in result_plan.completed if step.tool_name == "bash"]
        assert len([step for step in result_plan.completed if step.tool_name == 'bash']) >= 1
        bash_step = bash_steps[0]
        assert bash_step.status == "SUCCESS"
        assert bash_step.result is not None

    @pytest.mark.asyncio
    async def test_plan_execution_with_multiple_steps(self):
        """Test plan execution with multiple steps in sequence."""
        # Import at test time to avoid circular imports
        from unittest.mock import AsyncMock

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

        # Mock the agent's review_plan to just return the plan unchanged when LLM disabled
        for agent in orchestrator.agents.values():
            agent.review_plan = AsyncMock(side_effect=lambda p: p)

        # Execute the plan
        result_plan = await orchestrator.process_task(plan=plan)

        # Verify all steps executed successfully
        assert result_plan.is_complete
        assert not result_plan.has_failed
        # Check that our steps were completed (may include additional user_message steps)
        assert len([step for step in result_plan.completed if step.tool_name in ['write', 'bash']]) >= len(steps)

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

        # Test ANSI support detection (now in console)
        assert hasattr(orchestrator.console, 'supports_ansi')
        assert isinstance(orchestrator.console.supports_ansi, bool)

    @pytest.mark.asyncio
    async def test_output_summarization_behavior(self):
        """Test that output summarization works correctly."""
        # Import at test time to avoid circular imports
        from unittest.mock import AsyncMock

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

        # Mock the agent's review_plan to just return the plan unchanged when LLM disabled
        for agent in orchestrator.agents.values():
            agent.review_plan = AsyncMock(side_effect=lambda p: p)

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
        assert "SUCCESS" in output_content or "completed" in output_content



    @pytest.mark.asyncio
    async def test_long_output_command_with_output_replacement(self):
        """Test that long-running commands show full output during execution, then replace with summary."""
        # Import at test time to avoid circular imports
        from unittest.mock import AsyncMock

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

        # Mock the agent's review_plan to just return the plan unchanged when LLM disabled
        for agent in orchestrator.agents.values():
            agent.review_plan = AsyncMock(side_effect=lambda p: p)

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
        assert "remaining" in full_output or "SUCCESS" in full_output

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