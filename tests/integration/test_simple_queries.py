"""Integration tests using ClayOrchestrator directly to test Plan objects and tool calls."""

import pytest
from pathlib import Path

from clay.orchestrator.orchestrator import ClayOrchestrator
from clay.runtime.plan import PlanStatus


@pytest.mark.asyncio
async def test_basic_math():
    """Test basic math operations - should use LLM agent with no tool calls."""
    orchestrator = ClayOrchestrator()

    test_cases = [
        ("what is 2+2?", "4"),
        ("what is 5 * 7?", "35"),
        ("what is 10 / 2?", "5"),
        ("what is 8 - 3?", "5"),
    ]

    for query, expected_answer in test_cases:
        plan = await orchestrator.process_task(query)

        # Verify plan structure
        assert plan.status == PlanStatus.COMPLETED, f"Plan should be completed: {plan.error}"
        assert plan.output, "Plan should have output"
        assert len(plan.steps) == 0, "Math queries should not require tool execution"
        assert not plan.error, f"Plan should not have errors: {plan.error}"

        # Verify response content
        assert expected_answer in plan.output, f"Expected '{expected_answer}' in response: {plan.output}"


@pytest.mark.asyncio
async def test_simple_facts():
    """Test simple factual questions - should use LLM agent with no tool calls."""
    orchestrator = ClayOrchestrator()

    test_cases = [
        ("What is the capital of France?", ["Paris"]),
        ("How many days are in a week?", ["7", "seven"]),
        ("What color do you get when you mix red and blue?", ["purple", "violet"]),
        ("What is H2O?", ["water"]),
    ]

    for query, expected_keywords in test_cases:
        plan = await orchestrator.process_task(query)

        # Verify plan structure
        assert plan.status == PlanStatus.COMPLETED, f"Plan should be completed: {plan.error}"
        assert plan.output, "Plan should have output"
        assert len(plan.steps) == 0, "Factual queries should not require tool execution"
        assert not plan.error, f"Plan should not have errors: {plan.error}"

        # Verify response content contains expected keywords
        response_lower = plan.output.lower()
        assert any(keyword.lower() in response_lower for keyword in expected_keywords), \
            f"None of {expected_keywords} found in response: {plan.output}"


@pytest.mark.asyncio
async def test_simple_definitions():
    """Test simple definition requests - should use LLM agent with no tool calls."""
    orchestrator = ClayOrchestrator()

    test_cases = [
        ("What is Python?", ["programming", "language"]),
        ("Define recursion", ["function", "itself", "recursion"]),
        ("What is JSON?", ["format", "data", "javascript"]),
        ("What is an API?", ["interface", "application", "programming"]),
    ]

    for query, expected_keywords in test_cases:
        plan = await orchestrator.process_task(query)

        # Verify plan structure
        assert plan.status == PlanStatus.COMPLETED, f"Plan should be completed: {plan.error}"
        assert plan.output, "Plan should have output"
        assert len(plan.steps) == 0, "Definition queries should not require tool execution"
        assert not plan.error, f"Plan should not have errors: {plan.error}"
        assert len(plan.output) >= 10, f"Response should be detailed: {len(plan.output)} chars"

        # Verify response content contains expected keywords
        response_lower = plan.output.lower()
        found_keywords = sum(1 for keyword in expected_keywords if keyword.lower() in response_lower)
        assert found_keywords > 0, f"At least one of {expected_keywords} should be found in response: {plan.output}"


@pytest.mark.asyncio
async def test_informational_queries():
    """Test informational queries that should use LLM agent with no tool calls."""
    orchestrator = ClayOrchestrator()

    info_queries = [
        ("What are the benefits of version control?", ["version", "control", "git"]),
        ("Explain what a database is", ["database", "data", "storage"]),
        ("What is the difference between Python and JavaScript?", ["python", "javascript", "programming"]),
    ]

    for query, expected_keywords in info_queries:
        plan = await orchestrator.process_task(query)

        # Verify plan structure - informational queries should not execute tools
        assert plan.status == PlanStatus.COMPLETED, f"Plan should be completed: {plan.error}"
        assert plan.output, "Plan should have output"
        assert len(plan.steps) == 0, "Informational queries should not require tool execution"
        assert not plan.error, f"Plan should not have errors: {plan.error}"
        assert len(plan.output) >= 10, f"Response should be detailed: {len(plan.output)} chars"

        # Verify response content contains expected keywords
        response_lower = plan.output.lower()
        found_keywords = sum(1 for keyword in expected_keywords if keyword.lower() in response_lower)
        assert found_keywords > 0, f"At least one of {expected_keywords} should be found in response: {plan.output}"


@pytest.mark.asyncio
async def test_actual_file_operations():
    """Test actual file operations that should use coding agent and execute tools."""
    orchestrator = ClayOrchestrator()

    file_operations = [
        ("list files in the current directory", "bash", "ls"),
        ("show the contents of this directory", "bash", "ls"),
    ]

    for query, expected_tool, expected_command in file_operations:
        plan = await orchestrator.process_task(query)

        # Verify plan structure - actual file operations should execute tools
        assert plan.status == PlanStatus.COMPLETED, f"Plan should be completed: {plan.error}"
        assert len(plan.steps) > 0, f"File operations should require tool execution: {query}"
        assert not plan.error, f"Plan should not have errors: {plan.error}"

        # Verify first step uses expected tool
        first_step = plan.steps[0]
        assert first_step.tool_name == expected_tool, f"Expected {expected_tool} tool, got {first_step.tool_name}"
        assert first_step.status == PlanStatus.COMPLETED, f"Tool execution should be completed"

        # Verify tool parameters contain expected command
        if expected_tool == "bash":
            assert "command" in first_step.parameters, "Bash tool should have command parameter"
            command = first_step.parameters["command"]
            assert expected_command in command, f"Expected '{expected_command}' in command: {command}"


@pytest.mark.asyncio
async def test_simple_comparisons():
    """Test simple comparison questions - should use LLM agent with no tool calls."""
    orchestrator = ClayOrchestrator()

    test_cases = [
        ("Is 5 greater than 3?", ["yes", "true", "greater"]),
        ("Which is larger: 10 or 7?", ["10", "ten"]),
        ("Is Python a programming language?", ["yes", "true", "programming"]),
        ("What comes after Monday?", ["tuesday"]),
    ]

    for query, expected_keywords in test_cases:
        plan = await orchestrator.process_task(query)

        # Verify plan structure
        assert plan.status == PlanStatus.COMPLETED, f"Plan should be completed: {plan.error}"
        assert plan.output, "Plan should have output"
        assert len(plan.steps) == 0, "Comparison queries should not require tool execution"
        assert not plan.error, f"Plan should not have errors: {plan.error}"

        # Verify response content contains expected keywords
        response_lower = plan.output.lower()
        assert any(keyword.lower() in response_lower for keyword in expected_keywords), \
            f"None of {expected_keywords} found in response: {plan.output}"


@pytest.mark.asyncio
async def test_coding_tasks_with_tool_execution():
    """Test that actual coding tasks use coding agent and execute tools."""
    orchestrator = ClayOrchestrator()

    coding_tasks = [
        ("Create a Python file that prints hello world", "bash", "hello"),
        ("Create a Python script with fibonacci function", "bash", "fibonacci"),
        ("Write a script file that reads text files", "bash", "read"),
    ]

    for query, expected_tool, expected_content in coding_tasks:
        plan = await orchestrator.process_task(query)

        # Verify plan structure - coding tasks should execute tools
        assert plan.status == PlanStatus.COMPLETED, f"Plan should be completed: {plan.error}"
        assert len(plan.steps) > 0, f"Coding tasks should require tool execution: {query}"
        assert not plan.error, f"Plan should not have errors: {plan.error}"

        # Verify first step uses expected tool
        first_step = plan.steps[0]
        assert first_step.tool_name == expected_tool, f"Expected {expected_tool} tool, got {first_step.tool_name}"
        assert first_step.status == PlanStatus.COMPLETED, f"Tool execution should be completed"

        # Verify tool parameters contain expected content
        if expected_tool == "bash":
            assert "command" in first_step.parameters, "Bash tool should have command parameter"
            command_lower = first_step.parameters["command"].lower()
            assert expected_content in command_lower, f"Expected '{expected_content}' in bash command"