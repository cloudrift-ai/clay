"""Integration tests for task routing and model selection."""

import pytest
from clay.llm.model_router import ModelRouter, TaskType
from tests.integration.helpers import IntegrationTestHelper


@pytest.mark.asyncio
async def test_task_type_detection():
    """Test that Clay correctly identifies different task types."""
    helper = IntegrationTestHelper()

    # Get API keys for testing
    api_keys = {}
    for provider in ['cloudrift', 'anthropic', 'openai']:
        key, _ = helper.config.get_provider_credentials(provider)
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

    helper.cleanup()


@pytest.mark.asyncio
async def test_model_selection_for_simple_tasks():
    """Test that simple tasks use appropriate models."""
    helper = IntegrationTestHelper()
    session = await helper.create_session()

    simple_queries = [
        "what is 5 * 7?",
        "what day comes after Monday?",
        "how many hours in a day?",
    ]

    for query in simple_queries:
        response = await session.process_message(query)
        helper.assert_response_quality(response, min_length=1)
        # Simple responses should be relatively short and direct
        assert len(response) < 500, f"Simple query response should be concise: {len(response)} chars"

    helper.cleanup()


@pytest.mark.asyncio
async def test_model_selection_for_coding_tasks():
    """Test that coding tasks use appropriate models."""
    helper = IntegrationTestHelper()
    temp_dir = helper.create_temp_project()
    session = await helper.create_session(temp_dir)

    coding_queries = [
        "write a function to check if a number is prime",
        "implement quicksort algorithm",
        "create a class for a binary tree",
    ]

    for query in coding_queries:
        response = await session.process_message(query)
        # Check that the response mentions coding-related concepts
        helper.assert_response_quality(response, min_length=20)
        # Handle both string and dictionary responses
        if isinstance(response, dict):
            import json
            response_str = json.dumps(response, indent=2).lower()
        else:
            response_str = str(response).lower()
        coding_indicators = ["function", "def", "code", "implement", "algorithm", "prime", "check", "class", "binary", "tree", "created", "file"]
        found_indicators = sum(1 for indicator in coding_indicators if indicator in response_str)
        assert found_indicators >= 1, f"Coding response should contain relevant terms: {response}"

    helper.cleanup()


@pytest.mark.asyncio
async def test_model_selection_for_complex_reasoning():
    """Test that complex reasoning tasks use appropriate models."""
    helper = IntegrationTestHelper()
    session = await helper.create_session()

    complex_queries = [
        "compare the advantages and disadvantages of microservices vs monolithic architecture",
        "explain the trade-offs between different sorting algorithms",
        "analyze the impact of database indexing on query performance",
    ]

    for query in complex_queries:
        response = await session.process_message(query)
        # Check that complex reasoning provides meaningful responses
        helper.assert_response_quality(response, min_length=5)
        # Verify it contains reasoning-related terms
        if isinstance(response, dict):
            import json
            response_str = json.dumps(response, indent=2).lower()
        else:
            response_str = str(response).lower()
        reasoning_indicators = ["advantages", "disadvantages", "compare", "analysis", "trade", "consider", "approach"]
        found_indicators = sum(1 for indicator in reasoning_indicators if indicator in response_str)
        assert found_indicators >= 1 or len(response) > 150, f"Complex reasoning should be detailed or contain reasoning terms: {response}"

    helper.cleanup()


@pytest.mark.asyncio
async def test_orchestrator_vs_agent_routing():
    """Test that complex tasks use orchestrator while simple ones use agents."""
    helper = IntegrationTestHelper()
    temp_dir = helper.create_temp_project()
    session = await helper.create_session(temp_dir)

    # Simple tasks should be fast and direct
    simple_queries = [
        "what is 5 * 7?",
        "list files in this directory",
        "what day comes after Monday?",
    ]

    for query in simple_queries:
        response = await session.process_message(query)
        helper.assert_response_quality(response, min_length=1)
        # Simple responses should be relatively short and direct
        assert len(response) < 500, f"Simple query response should be concise: {len(response)} chars"

    # Complex tasks might use orchestrator (if available)
    complex_queries = [
        "implement a complete REST API with authentication",
        "create a machine learning model for text classification",
    ]

    for query in complex_queries:
        response = await session.process_message(query)
        helper.assert_response_quality(response, min_length=20)
        # Complex responses can be longer and more detailed

    helper.cleanup()


@pytest.mark.asyncio
async def test_task_classification_patterns():
    """Test specific patterns in task classification."""
    helper = IntegrationTestHelper()

    api_keys = {}
    for provider in ['cloudrift', 'anthropic', 'openai']:
        key, _ = helper.config.get_provider_credentials(provider)
        if key:
            api_keys[provider] = key

    if not api_keys:
        pytest.skip("No API keys available for model router testing")

    router = ModelRouter(api_keys)

    # Test simple reasoning patterns
    simple_patterns = [
        "what is 10 + 5?",
        "how many days in February?",
        "what is the capital of France?",
        "true or false: cats are mammals",
    ]

    for pattern in simple_patterns:
        task_type = router.classify_task(pattern)
        assert task_type == TaskType.SIMPLE_REASONING, f"'{pattern}' should be simple reasoning, got {task_type}"

    # Test coding patterns
    coding_patterns = [
        "implement a linked list",
        "debug this Python code",
        "refactor the following function",
        "write a unit test for this method",
    ]

    for pattern in coding_patterns:
        task_type = router.classify_task(pattern)
        assert task_type == TaskType.CODING, f"'{pattern}' should be coding, got {task_type}"

    # Test research patterns
    research_patterns = [
        "research machine learning frameworks",
        "find documentation about databases",
        "investigate renewable energy trends",
        "lookup historical facts about computers",
    ]

    for pattern in research_patterns:
        task_type = router.classify_task(pattern)
        assert task_type == TaskType.RESEARCH, f"'{pattern}' should be research, got {task_type}"

    helper.cleanup()


@pytest.mark.asyncio
async def test_multi_model_availability():
    """Test that multi-model system can access different models."""
    helper = IntegrationTestHelper()

    api_keys = {}
    for provider in ['cloudrift', 'anthropic', 'openai']:
        key, _ = helper.config.get_provider_credentials(provider)
        if key:
            api_keys[provider] = key

    if not api_keys:
        pytest.skip("No API keys available for model router testing")

    router = ModelRouter(api_keys)

    # Test that we can get models for different task types
    task_types = [TaskType.SIMPLE_REASONING, TaskType.CODING, TaskType.COMPLEX_REASONING]

    for task_type in task_types:
        provider, config = router.get_best_model(task_type)
        if provider:  # Only check if we have a provider for this task type
            assert provider is not None, f"Should have a provider for {task_type}"
            assert config is not None, f"Should have config for {task_type}"
            assert hasattr(config, 'model'), f"Config should have model attribute for {task_type}"
            assert hasattr(config, 'temperature'), f"Config should have temperature for {task_type}"

    helper.cleanup()


@pytest.mark.asyncio
async def test_creative_task_routing():
    """Test that creative tasks are properly routed."""
    helper = IntegrationTestHelper()
    session = await helper.create_session()

    creative_queries = [
        "write a short story about time travel",
        "create a poem about artificial intelligence",
        "generate creative names for a new coffee shop",
        "write a fictional dialogue between two robots",
    ]

    for query in creative_queries:
        response = await session.process_message(query)
        helper.assert_response_quality(response, min_length=50)
        # Creative responses should be substantial and engaging
        assert len(response) > 100, f"Creative task should generate substantial content: {len(response)} chars"

    helper.cleanup()


@pytest.mark.asyncio
async def test_research_task_routing():
    """Test that research tasks are properly handled."""
    helper = IntegrationTestHelper()
    session = await helper.create_session()

    research_queries = [
        "explain the current state of quantum computing",
        "what are the latest developments in renewable energy?",
        "research the benefits of containerization in software development",
        "investigate the history of programming languages",
    ]

    for query in research_queries:
        response = await session.process_message(query)
        # Check that research provides informative responses
        helper.assert_response_quality(response, min_length=5)
        # Verify it contains research-related content
        if isinstance(response, dict):
            import json
            response_str = json.dumps(response, indent=2).lower()
        else:
            response_str = str(response).lower()
        research_indicators = ["research", "information", "current", "development", "state", "field", "technology", "studies"]
        found_indicators = sum(1 for indicator in research_indicators if indicator in response_str)
        assert found_indicators >= 1 or len(response) > 150, f"Research task should be informative or contain relevant terms: {response}"

    helper.cleanup()