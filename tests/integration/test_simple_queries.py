"""Integration tests using ClayOrchestrator directly to test Plan objects and tool calls."""

import pytest
from pathlib import Path

from clay.orchestrator.orchestrator import ClayOrchestrator


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
        # Plan should have completed successfully (check for message steps)
        # Plan should have completed with message steps
        assert len(plan.completed) > 0, "Plan should have completed steps"
        # Check for message tool usage in completed steps
        message_steps = [step for step in plan.completed if step.tool_name == "message"]
        assert len(message_steps) > 0, "Plan should use message tool for responses"
        # Check that only message tools were used (no bash/file operations)
        non_message_steps = [step for step in plan.steps if step.tool_name != "message"]
        assert len(non_message_steps) == 0, "Math queries should only use message tool"
        # Plan should have completed successfully (check for message steps)

        # Verify response content
        # Check that message contains expected answer
        message_content = message_steps[0].result.get("output", "") if message_steps[0].result else ""
        assert expected_answer in message_content, f"Expected '{expected_answer}' in response: {message_content}"


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
        # Plan should have completed successfully (check for message steps)
        # Plan should have completed with message steps
        assert len(plan.completed) > 0, "Plan should have completed steps"
        # Check for message tool usage in completed steps
        message_steps = [step for step in plan.completed if step.tool_name == "message"]
        assert len(message_steps) > 0, "Plan should use message tool for responses"
        # Check that only message tools were used (no bash/file operations)
        non_message_steps = [step for step in plan.steps if step.tool_name != "message"]
        assert len(non_message_steps) == 0, "Factual queries should only use message tool"
        # Plan should have completed successfully (check for message steps)

        # Verify response content contains expected keywords
        message_content = message_steps[0].result.get("output", "") if message_steps[0].result else ""
        response_lower = message_content.lower()
        assert any(keyword.lower() in response_lower for keyword in expected_keywords), \
            f"None of {expected_keywords} found in response: {message_content}"


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
        # Plan should have completed successfully (check for message steps)
        # Plan should have completed with message steps
        assert len(plan.completed) > 0, "Plan should have completed steps"
        # Check for message tool usage in completed steps
        message_steps = [step for step in plan.completed if step.tool_name == "message"]
        assert len(message_steps) > 0, "Plan should use message tool for responses"
        # Check that only message tools were used (no bash/file operations)
        non_message_steps = [step for step in plan.steps if step.tool_name != "message"]
        assert len(non_message_steps) == 0, "Definition queries should only use message tool"
        # Plan should have completed successfully (check for message steps)

        # Verify response content contains expected keywords
        message_content = message_steps[0].result.get("output", "") if message_steps[0].result else ""
        assert len(message_content) >= 10, f"Response should be detailed: {len(message_content)} chars"
        response_lower = message_content.lower()
        found_keywords = sum(1 for keyword in expected_keywords if keyword.lower() in response_lower)
        assert found_keywords > 0, f"At least one of {expected_keywords} should be found in response: {message_content}"


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
        # Plan should have completed successfully (check for message steps)
        # Plan should have completed with message steps
        assert len(plan.completed) > 0, "Plan should have completed steps"
        # Check for message tool usage in completed steps
        message_steps = [step for step in plan.completed if step.tool_name == "message"]
        assert len(message_steps) > 0, "Plan should use message tool for responses"
        # Check that only message tools were used (no bash/file operations)
        non_message_steps = [step for step in plan.steps if step.tool_name != "message"]
        assert len(non_message_steps) == 0, "Informational queries should only use message tool"
        # Plan should have completed successfully (check for message steps)

        # Verify response content contains expected keywords
        message_content = message_steps[0].result.get("output", "") if message_steps[0].result else ""
        assert len(message_content) >= 10, f"Response should be detailed: {len(message_content)} chars"
        response_lower = message_content.lower()
        found_keywords = sum(1 for keyword in expected_keywords if keyword.lower() in response_lower)
        assert found_keywords > 0, f"At least one of {expected_keywords} should be found in response: {message_content}"


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
        # Plan should have completed successfully (check for message steps)
        assert len(plan.steps) > 0, f"File operations should require tool execution: {query}"
        # Plan should have completed successfully (check for message steps)

        # Verify first step uses expected tool
        first_step = plan.steps[0]
        assert first_step.tool_name == expected_tool, f"Expected {expected_tool} tool, got {first_step.tool_name}"
        assert first_step.result is not None, f"Tool execution should have a result"

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
        # Plan should have completed successfully (check for message steps)
        # Plan should have completed with message steps
        assert len(plan.completed) > 0, "Plan should have completed steps"
        # Check for message tool usage in completed steps
        message_steps = [step for step in plan.completed if step.tool_name == "message"]
        assert len(message_steps) > 0, "Plan should use message tool for responses"
        # Check that only message tools were used (no bash/file operations)
        non_message_steps = [step for step in plan.steps if step.tool_name != "message"]
        assert len(non_message_steps) == 0, "Comparison queries should only use message tool"
        # Plan should have completed successfully (check for message steps)

        # Verify response content contains expected keywords
        message_content = message_steps[0].result.get("output", "") if message_steps[0].result else ""
        response_lower = message_content.lower()
        assert any(keyword.lower() in response_lower for keyword in expected_keywords), \
            f"None of {expected_keywords} found in response: {message_content}"


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
        # Plan should have completed successfully (check for message steps)
        assert len(plan.steps) > 0, f"Coding tasks should require tool execution: {query}"
        # Plan should have completed successfully (check for message steps)

        # Verify first step uses expected tool
        first_step = plan.steps[0]
        assert first_step.tool_name == expected_tool, f"Expected {expected_tool} tool, got {first_step.tool_name}"
        assert first_step.result is not None, f"Tool execution should have a result"

        # Verify tool parameters contain expected content
        if expected_tool == "bash":
            assert "command" in first_step.parameters, "Bash tool should have command parameter"
            command_lower = first_step.parameters["command"].lower()
            assert expected_content in command_lower, f"Expected '{expected_content}' in bash command"