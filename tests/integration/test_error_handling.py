"""Integration tests for error handling and edge cases."""

import pytest
from tests.integration.helpers import IntegrationTestHelper


@pytest.mark.asyncio
async def test_invalid_file_operations():
    """Test handling of invalid file operations."""
    helper = IntegrationTestHelper()
    temp_dir = helper.create_temp_project()
    session = await helper.create_session(temp_dir)

    test_cases = [
        "read nonexistent_file.txt",
        "list files in /nonexistent/directory",
        "show contents of empty_directory",
    ]

    for query in test_cases:
        response = await session.process_message(query)
        # Should handle errors gracefully
        assert response, "Should provide some response even for invalid operations"
        # Response should be reasonable
        helper.assert_response_quality(response, min_length=5)

    helper.cleanup()


@pytest.mark.asyncio
async def test_ambiguous_queries():
    """Test handling of ambiguous or unclear queries."""
    helper = IntegrationTestHelper()
    session = await helper.create_session()

    ambiguous_queries = [
        "help",
        "what?",
        "do something",
        "fix it",
        "make it better",
    ]

    for query in ambiguous_queries:
        response = await session.process_message(query)
        # Should provide some response even for ambiguous queries
        assert response, f"Should provide response for ambiguous query: {query}"
        assert len(response) > 5, "Response should be meaningful"

    helper.cleanup()


@pytest.mark.asyncio
async def test_empty_and_whitespace_queries():
    """Test handling of empty or whitespace-only queries."""
    helper = IntegrationTestHelper()
    session = await helper.create_session()

    edge_case_queries = [
        "   ",  # Just spaces
        "\t\n",  # Tabs and newlines
        "",  # Empty string
        "?",  # Just a question mark
        "...",  # Just dots
    ]

    for query in edge_case_queries:
        if query.strip():  # Only test non-empty queries
            response = await session.process_message(query)
            # Should handle gracefully
            assert response, f"Should provide response for edge case: '{query}'"

    helper.cleanup()


@pytest.mark.asyncio
async def test_special_characters_in_queries():
    """Test handling of queries with special characters."""
    helper = IntegrationTestHelper()
    session = await helper.create_session()

    special_queries = [
        "what is 2+2? !@#$%^&*()",
        "explain python's \"list comprehension\" feature",
        "how does the $ symbol work in regex?",
        "what about file paths like /home/user/file.txt?",
    ]

    for query in special_queries:
        response = await session.process_message(query)
        # Should handle special characters gracefully
        assert response, f"Should handle special characters in: '{query}'"
        helper.assert_response_quality(response, min_length=10)

    helper.cleanup()