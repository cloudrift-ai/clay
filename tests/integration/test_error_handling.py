"""Integration tests for error handling and edge cases."""

import pytest
from pathlib import Path
from tests.integration.test_helpers import run_clay_command, assert_response_quality


@pytest.mark.asyncio
async def test_invalid_file_operations():
    """Test handling of invalid file operations."""
    test_cases = [
        "read nonexistent_file.txt",
        "list files in /nonexistent/directory",
        "show contents of empty_directory",
    ]

    for query in test_cases:
        response = await run_clay_command(query)
        # Should handle errors gracefully
        assert response, "Should provide some response even for invalid operations"
        # Response should be reasonable
        assert_response_quality(response, min_length=5)


@pytest.mark.asyncio
async def test_ambiguous_queries():
    """Test handling of ambiguous or unclear queries."""
    ambiguous_queries = [
        "help",
        "what?",
        "do something",
        "fix it",
        "make it better",
    ]

    for query in ambiguous_queries:
        response = await run_clay_command(query)
        # Should provide some response even for ambiguous queries
        assert response, f"Should provide response for ambiguous query: {query}"
        assert len(response) > 5, "Response should be meaningful"


@pytest.mark.asyncio
async def test_empty_and_whitespace_queries():
    """Test handling of empty or whitespace-only queries."""
    edge_case_queries = [
        "   ",  # Just spaces
        "?",  # Just a question mark
        "...",  # Just dots
    ]

    for query in edge_case_queries:
        if query.strip():  # Only test non-empty queries
            response = await run_clay_command(query)
            # Should handle gracefully
            assert response, f"Should provide response for edge case: '{query}'"


@pytest.mark.asyncio
async def test_special_characters_in_queries():
    """Test handling of queries with special characters."""
    special_queries = [
        "what is 2+2? !@#$%^&*()",
        "explain python's \"list comprehension\" feature",
        "how does the $ symbol work in regex?",
        "what about file paths like /home/user/file.txt?",
    ]

    for query in special_queries:
        response = await run_clay_command(query)
        # Should handle special characters gracefully
        assert response, f"Should handle special characters in: '{query}'"
        assert_response_quality(response, min_length=10)