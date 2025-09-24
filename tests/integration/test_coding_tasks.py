"""Integration tests for coding-related queries."""

import pytest
from pathlib import Path
from tests.integration.helpers import IntegrationTestHelper


@pytest.mark.asyncio
async def test_simple_function_creation():
    """Test creating simple functions."""
    helper = IntegrationTestHelper()
    temp_dir = helper.create_temp_project()
    session = await helper.create_session(temp_dir)

    test_cases = [
        {
            "query": "write a function to calculate factorial",
            "expected_content": ["def factorial", "return", "for", "range"]
        },
        {
            "query": "create a function to reverse a string",
            "expected_content": ["def", "reverse", "string", "return"]
        },
        {
            "query": "implement bubble sort algorithm",
            "expected_content": ["def", "bubble", "sort", "for", "if"]
        }
    ]

    for test_case in test_cases:
        response = await session.process_message(test_case["query"])
        helper.assert_response_quality(response, min_length=20)

        # Check if files were created (may not always happen in simple mode)
        created_files = list(temp_dir.glob("*.py"))
        if created_files:
            # If files were created, verify content
            for file_path in created_files:
                content = file_path.read_text().lower()
                # Check for at least some expected content
                found_content = any(keyword in content for keyword in test_case["expected_content"])
                assert found_content, f"Expected content not found in {file_path}"

    helper.cleanup()


@pytest.mark.asyncio
async def test_code_explanation():
    """Test code explanation capabilities."""
    helper = IntegrationTestHelper()
    temp_dir = helper.create_temp_project()
    session = await helper.create_session(temp_dir)

    # Create a sample Python file
    sample_code = '''
def quicksort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)
'''
    code_file = temp_dir / "quicksort.py"
    code_file.write_text(sample_code)

    test_cases = [
        ("explain the quicksort.py file", ["quicksort", "algorithm", "pivot", "recursive"]),
        ("how does the quicksort function work?", ["sort", "divide", "conquer"]),
        ("what is the time complexity of this algorithm?", ["O(n", "complexity", "log"]),
    ]

    for query, expected_keywords in test_cases:
        response = await session.process_message(query)
        helper.assert_response_quality(response, expected_keywords, min_length=50)

    helper.cleanup()


@pytest.mark.asyncio
async def test_algorithm_implementation():
    """Test implementation of common algorithms."""
    helper = IntegrationTestHelper()
    temp_dir = helper.create_temp_project()
    session = await helper.create_session(temp_dir)

    algorithms = [
        "implement binary search",
        "write a merge sort function",
        "create a function to find the maximum element in an array",
        "implement a function to check if a string is a palindrome",
    ]

    for algorithm_request in algorithms:
        response = await session.process_message(algorithm_request)
        helper.assert_response_quality(response, ["function", "def"], min_length=30)

        # Check if any Python files were created
        py_files = list(temp_dir.glob("*.py"))
        if py_files:
            # Verify that created files contain actual code
            for file_path in py_files:
                content = file_path.read_text()
                assert "def " in content, f"Python file should contain function definition: {file_path}"
                assert len(content.strip()) > 50, f"Code file should have substantial content: {file_path}"

    helper.cleanup()


@pytest.mark.asyncio
async def test_code_debugging():
    """Test code debugging and fixing capabilities."""
    helper = IntegrationTestHelper()
    temp_dir = helper.create_temp_project()
    session = await helper.create_session(temp_dir)

    # Create a buggy Python file
    buggy_code = '''
def fibonacci(n):
    if n <= 0:
        return 0
    elif n == 1:
        return 1
    else:
        return fibonacci(n-1) + fibonacci(n-2
'''
    buggy_file = temp_dir / "buggy_fibonacci.py"
    buggy_file.write_text(buggy_code)

    queries = [
        "fix the syntax error in buggy_fibonacci.py",
        "what's wrong with the fibonacci function?",
        "debug the code in buggy_fibonacci.py",
    ]

    for query in queries:
        response = await session.process_message(query)
        # Should identify the issue
        helper.assert_response_quality(response, ["error", "syntax", "missing"], min_length=20)

    helper.cleanup()


@pytest.mark.asyncio
async def test_code_optimization():
    """Test code optimization suggestions."""
    helper = IntegrationTestHelper()
    temp_dir = helper.create_temp_project()
    session = await helper.create_session(temp_dir)

    # Create an inefficient implementation
    inefficient_code = '''
def find_max(numbers):
    max_num = numbers[0]
    for i in range(len(numbers)):
        for j in range(len(numbers)):
            if numbers[j] > max_num:
                max_num = numbers[j]
    return max_num
'''
    code_file = temp_dir / "inefficient.py"
    code_file.write_text(inefficient_code)

    queries = [
        "optimize the find_max function",
        "how can I improve the performance of this code?",
        "suggest better algorithms for finding maximum",
    ]

    for query in queries:
        response = await session.process_message(query)
        helper.assert_response_quality(response, ["optimize", "improve", "efficient"], min_length=30)

    helper.cleanup()


@pytest.mark.asyncio
async def test_class_creation():
    """Test creating Python classes."""
    helper = IntegrationTestHelper()
    temp_dir = helper.create_temp_project()
    session = await helper.create_session(temp_dir)

    class_requests = [
        "create a simple Person class with name and age attributes",
        "implement a Stack class with push and pop methods",
        "write a BankAccount class with deposit and withdraw methods",
    ]

    for request in class_requests:
        response = await session.process_message(request)
        helper.assert_response_quality(response, ["class"], min_length=30)

        # Check if any Python files were created with class definitions
        py_files = list(temp_dir.glob("*.py"))
        if py_files:
            for file_path in py_files:
                content = file_path.read_text()
                assert "class " in content, f"Should contain class definition: {file_path}"

    helper.cleanup()


@pytest.mark.asyncio
async def test_unit_test_creation():
    """Test creating unit tests for code."""
    helper = IntegrationTestHelper()
    temp_dir = helper.create_temp_project()
    session = await helper.create_session(temp_dir)

    # Create a simple function to test
    function_code = '''
def add_numbers(a, b):
    """Add two numbers together."""
    return a + b

def multiply(x, y):
    """Multiply two numbers."""
    return x * y
'''
    code_file = temp_dir / "math_utils.py"
    code_file.write_text(function_code)

    test_requests = [
        "create unit tests for the functions in math_utils.py",
        "write pytest tests for the add_numbers function",
        "generate test cases for multiply function",
    ]

    for request in test_requests:
        response = await session.process_message(request)
        helper.assert_response_quality(response, ["test", "assert"], min_length=30)

    helper.cleanup()