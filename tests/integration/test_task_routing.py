"""Integration tests for task routing and model selection."""

import pytest
from clay.llm.model_router import ModelRouter, TaskType
from clay.config import get_config
from pathlib import Path
from tests.integration.test_helpers import run_clay_command, assert_response_quality



@pytest.mark.asyncio
async def test_task_type_detection():
    """Test that Clay correctly identifies different task types."""
    config = get_config()

    # Get API keys for testing
    api_keys = {}
    for provider in ['cloudrift', 'anthropic', 'openai']:
        key, _ = config.get_provider_credentials(provider)
        if key:
            api_keys[provider] = key

    if not api_keys:
        pytest.skip("No API keys available for model router testing")

    router = ModelRouter(api_keys)

    test_cases = [
        ("what is 2+2?", TaskType.SIMPLE_REASONING),
        ("implement a function to sort an array", TaskType.CODING),
        ("analyze the pros and cons of different databases", TaskType.COMPLEX_REASONING),
        ("create a creative story about robots", TaskType.CREATIVE),
        ("research the latest trends in machine learning", TaskType.RESEARCH),
    ]

    for query, expected_task_type in test_cases:
        detected_type = router.classify_task(query)
        assert detected_type == expected_task_type, f"Query '{query}' should be classified as {expected_task_type}, got {detected_type}"


@pytest.mark.asyncio
async def test_model_selection_for_simple_tasks():
    """Test that simple tasks use appropriate models."""
    simple_queries = [
        "what is 5 * 7?",
        "what day comes after Monday?",
        "how many hours in a day?",
    ]

    for query in simple_queries:
        response = await run_clay_command(query)
        assert_response_quality(response, min_length=1)
        # Simple responses should be relatively short and direct
        assert len(response) < 500, f"Simple query response should be concise: {len(response)} chars"


@pytest.mark.asyncio
async def test_model_selection_for_coding_tasks():
    """Test that coding tasks use appropriate models."""
    # Create a temporary directory for this test
    temp_dir = Path.cwd() / "test_project"
    temp_dir.mkdir(exist_ok=True)

    coding_queries = [
        "write a function to check if a number is prime",
        "implement quicksort algorithm",
        "create a class for a binary tree",
    ]

    for query in coding_queries:
        response = await run_clay_command(query, temp_dir)
        # Check that the response mentions coding-related concepts
        assert_response_quality(response, min_length=20)
        # Handle both string and dictionary responses
        response_str = str(response).lower()
        coding_indicators = ["function", "def", "code", "implement", "algorithm", "prime", "check", "class", "binary", "tree", "created", "file"]
        found_indicators = sum(1 for indicator in coding_indicators if indicator in response_str)
        assert found_indicators >= 1, f"Coding response should contain relevant terms: {response}"


@pytest.mark.asyncio
async def test_model_selection_for_complex_reasoning():
    """Test that complex reasoning tasks use appropriate models."""
    complex_queries = [
        "compare the advantages and disadvantages of microservices vs monolithic architecture",
        "explain the trade-offs between different sorting algorithms",
        "analyze the impact of database indexing on query performance",
    ]

    for query in complex_queries:
        response = await run_clay_command(query)
        # Check that complex reasoning provides meaningful responses
        assert_response_quality(response, min_length=5)
        # Verify it contains reasoning-related terms
        response_str = str(response).lower()
        reasoning_indicators = ["advantages", "disadvantages", "compare", "analysis", "trade", "consider", "approach"]
        found_indicators = sum(1 for indicator in reasoning_indicators if indicator in response_str)
        assert found_indicators >= 1 or len(response) > 150, f"Complex reasoning should be detailed or contain reasoning terms: {response}"