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

            # Should contain tool execution summaries
            assert "⏺ Write(test.txt)" in output_content or "test.txt" in output_content

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