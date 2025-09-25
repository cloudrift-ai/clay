"""Integration tests for simple queries that should get direct answers."""

import os
import pytest
from pathlib import Path
from tests.integration.test_helpers import run_clay_command, assert_response_quality



@pytest.mark.asyncio
async def test_basic_math():
    """Test basic math operations."""
    test_cases = [
        ("what is 2+2?", "4"),
        ("what is 5 * 7?", "35"),
        ("what is 10 / 2?", "5"),
        ("what is 8 - 3?", "5"),
    ]

    for query, expected_answer in test_cases:
        response = await run_clay_command(query)
        assert_response_quality(response, [expected_answer], min_length=1)


@pytest.mark.asyncio
async def test_simple_facts():
    """Test simple factual questions."""
    test_cases = [
        ("What is the capital of France?", ["Paris"]),
        ("How many days are in a week?", ["7", "seven"]),
        ("What color do you get when you mix red and blue?", ["purple", "violet"]),
        ("What is H2O?", ["water"]),
    ]

    for query, expected_keywords in test_cases:
        response = await run_clay_command(query)
        # At least one of the expected keywords should be present
        assert_response_quality(response, min_length=3)
        response_lower = response.lower()
        assert any(keyword.lower() in response_lower for keyword in expected_keywords), \
            f"None of {expected_keywords} found in response: {response}"


@pytest.mark.asyncio
async def test_simple_definitions():
    """Test simple definition requests."""
    test_cases = [
        ("What is Python?", ["programming", "language"]),
        ("Define recursion", ["function", "itself", "recursion"]),
        ("What is JSON?", ["format", "data", "javascript"]),
        ("What is an API?", ["interface", "application", "programming"]),
    ]

    for query, expected_keywords in test_cases:
        response = await run_clay_command(query)
        assert_response_quality(response, expected_keywords, min_length=10)


@pytest.mark.asyncio
async def test_file_operations():
    """Test basic file operation queries."""
    # Create a test file in current directory
    test_file = Path("test.txt")
    test_file.write_text("Hello, World!\nThis is a test file.\n")

    file_queries = [
        "list files in the current directory",
        "show the contents of test.txt",
        "what files are in this directory?",
    ]

    for query in file_queries:
        response = await run_clay_command(query)
        assert_response_quality(response, min_length=5)


@pytest.mark.asyncio
async def test_simple_comparisons():
    """Test simple comparison questions."""
    test_cases = [
        ("Is 5 greater than 3?", ["yes", "true", "greater"]),
        ("Which is larger: 10 or 7?", ["10", "ten"]),
        ("Is Python a programming language?", ["yes", "true", "programming"]),
        ("What comes after Monday?", ["tuesday"]),
    ]

    for query, expected_keywords in test_cases:
        response = await run_clay_command(query)
        assert_response_quality(response, min_length=1)
        response_lower = response.lower()
        assert any(keyword.lower() in response_lower for keyword in expected_keywords), \
            f"None of {expected_keywords} found in response: {response}"