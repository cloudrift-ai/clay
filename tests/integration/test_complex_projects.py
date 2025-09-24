"""Integration tests for complex multi-step project creation."""

import pytest
from pathlib import Path
from tests.integration.helpers import IntegrationTestHelper


@pytest.mark.slow
@pytest.mark.asyncio
async def test_simple_web_server_project():
    """Test creating a simple web server project."""
    helper = IntegrationTestHelper()
    temp_dir = helper.create_temp_project("web_server")
    session = await helper.create_session(temp_dir)

    query = "Create a simple Python web server project with Flask. Include a main app file, a requirements.txt, and a simple HTML template."

    response = await session.process_message(query)
    helper.assert_response_quality(response, ["flask", "server", "app"], min_length=50)

    # Check if project structure was created
    expected_files = [
        "app.py",
        "requirements.txt",
    ]

    # Some files might be created
    created_files = list(temp_dir.glob("**/*.py")) + list(temp_dir.glob("**/*.txt"))
    if created_files:
        # Verify content quality if files were created
        for file_path in created_files:
            assert file_path.stat().st_size > 10, f"File {file_path} is too small"

    helper.cleanup()


@pytest.mark.slow
@pytest.mark.asyncio
async def test_calculator_project():
    """Test creating a calculator project."""
    helper = IntegrationTestHelper()
    temp_dir = helper.create_temp_project("calculator")
    session = await helper.create_session(temp_dir)

    query = "Build a command-line calculator application in Python that can perform basic arithmetic operations (add, subtract, multiply, divide) with a menu system."

    response = await session.process_message(query)
    helper.assert_response_quality(response, ["calculator", "arithmetic", "menu"], min_length=50)

    # Check for calculator-related files
    py_files = list(temp_dir.glob("*.py"))
    if py_files:
        for file_path in py_files:
            content = file_path.read_text().lower()
            # Should contain calculator-related functions
            calculator_indicators = ["def", "add", "subtract", "multiply", "divide", "menu", "input"]
            found_indicators = sum(1 for indicator in calculator_indicators if indicator in content)
            assert found_indicators >= 3, f"Calculator file {file_path} should contain calculator logic"

    helper.cleanup()


@pytest.mark.slow
@pytest.mark.asyncio
async def test_data_analysis_project():
    """Test creating a data analysis project."""
    helper = IntegrationTestHelper()
    temp_dir = helper.create_temp_project("data_analysis")
    session = await helper.create_session(temp_dir)

    query = "Create a data analysis project that reads a CSV file, performs basic statistics, and generates visualizations. Include sample data and documentation."

    response = await session.process_message(query)
    helper.assert_response_quality(response, ["data", "analysis", "csv"], min_length=50)

    # Check for data analysis related files
    created_files = list(temp_dir.glob("**/*"))
    if created_files:
        file_extensions = [f.suffix for f in created_files if f.is_file()]
        # Should have some Python files
        assert any(ext == ".py" for ext in file_extensions), "Should create Python files for analysis"

    helper.cleanup()


@pytest.mark.asyncio
async def test_simple_cli_tool():
    """Test creating a simple CLI tool."""
    helper = IntegrationTestHelper()
    temp_dir = helper.create_temp_project("cli_tool")
    session = await helper.create_session(temp_dir)

    query = "Create a simple command-line tool in Python that counts lines in text files. Include argument parsing and help text."

    response = await session.process_message(query)
    helper.assert_response_quality(response, min_length=30)

    # Check if any Python files were created
    py_files = list(temp_dir.glob("*.py"))
    if py_files:
        for file_path in py_files:
            content = file_path.read_text().lower()
            # Should contain CLI-related code
            cli_indicators = ["argparse", "main", "if __name__", "def"]
            found_indicators = sum(1 for indicator in cli_indicators if indicator in content)
            assert found_indicators >= 2, f"CLI tool should contain appropriate structure: {file_path}"

    helper.cleanup()


@pytest.mark.asyncio
async def test_simple_game():
    """Test creating a simple game."""
    helper = IntegrationTestHelper()
    temp_dir = helper.create_temp_project("game")
    session = await helper.create_session(temp_dir)

    query = "Create a simple number guessing game in Python where the computer picks a random number and the user tries to guess it."

    response = await session.process_message(query)
    helper.assert_response_quality(response, ["game", "guess", "number"], min_length=30)

    # Check if game files were created
    py_files = list(temp_dir.glob("*.py"))
    if py_files:
        for file_path in py_files:
            content = file_path.read_text().lower()
            # Should contain game-related code
            game_indicators = ["random", "input", "guess", "while", "if"]
            found_indicators = sum(1 for indicator in game_indicators if indicator in content)
            assert found_indicators >= 3, f"Game should contain game logic: {file_path}"

    helper.cleanup()


@pytest.mark.slow
@pytest.mark.asyncio
async def test_rest_api_project():
    """Test creating a REST API project."""
    helper = IntegrationTestHelper()
    temp_dir = helper.create_temp_project("api")
    session = await helper.create_session(temp_dir)

    query = "Create a simple REST API using Flask with endpoints for CRUD operations on a user resource. Include basic error handling."

    response = await session.process_message(query)
    helper.assert_response_quality(response, ["api", "rest", "flask"], min_length=50)

    # Check if API files were created
    created_files = list(temp_dir.glob("**/*.py"))
    if created_files:
        for file_path in created_files:
            content = file_path.read_text().lower()
            # Should contain API-related code
            api_indicators = ["flask", "route", "get", "post", "put", "delete"]
            found_indicators = sum(1 for indicator in api_indicators if indicator in content)
            if found_indicators >= 3:
                # This file contains API logic
                assert "def" in content, f"API file should contain function definitions: {file_path}"

    helper.cleanup()


@pytest.mark.asyncio
async def test_utility_library():
    """Test creating a utility library."""
    helper = IntegrationTestHelper()
    temp_dir = helper.create_temp_project("utils")
    session = await helper.create_session(temp_dir)

    query = "Create a Python utility library with common string manipulation functions: capitalize_words, reverse_string, count_vowels, and remove_whitespace."

    response = await session.process_message(query)
    helper.assert_response_quality(response, ["utility", "function", "string"], min_length=30)

    # Check if utility files were created
    py_files = list(temp_dir.glob("*.py"))
    if py_files:
        for file_path in py_files:
            content = file_path.read_text().lower()
            # Should contain utility functions
            util_indicators = ["def", "capitalize", "reverse", "count", "remove"]
            found_indicators = sum(1 for indicator in util_indicators if indicator in content)
            assert found_indicators >= 3, f"Utility library should contain multiple functions: {file_path}"

    helper.cleanup()


@pytest.mark.slow
@pytest.mark.asyncio
async def test_todo_app_project():
    """Test creating a todo application."""
    helper = IntegrationTestHelper()
    temp_dir = helper.create_temp_project("todo_app")
    session = await helper.create_session(temp_dir)

    query = "Create a simple todo application with CLI interface. Users should be able to add, remove, list, and mark tasks as complete. Store tasks in a JSON file."

    response = await session.process_message(query)
    helper.assert_response_quality(response, ["todo", "task", "json"], min_length=50)

    # Check if todo app files were created
    created_files = list(temp_dir.glob("**/*"))
    if created_files:
        py_files = [f for f in created_files if f.suffix == ".py"]
        if py_files:
            for file_path in py_files:
                content = file_path.read_text().lower()
                # Should contain todo-related functionality
                todo_indicators = ["add", "remove", "list", "complete", "json", "task"]
                found_indicators = sum(1 for indicator in todo_indicators if indicator in content)
                assert found_indicators >= 3, f"Todo app should contain task management logic: {file_path}"

    helper.cleanup()


@pytest.mark.slow
@pytest.mark.asyncio
async def test_blog_generator():
    """Test creating a static blog generator."""
    helper = IntegrationTestHelper()
    temp_dir = helper.create_temp_project("blog_generator")
    session = await helper.create_session(temp_dir)

    query = "Create a static blog generator in Python that converts Markdown files to HTML. Include template support and a simple build script."

    response = await session.process_message(query)
    helper.assert_response_quality(response, ["blog", "markdown", "html"], min_length=50)

    # Check if blog generator files were created
    created_files = list(temp_dir.glob("**/*"))
    if created_files:
        py_files = [f for f in created_files if f.suffix == ".py"]
        if py_files:
            for file_path in py_files:
                content = file_path.read_text().lower()
                # Should contain blog generation logic
                blog_indicators = ["markdown", "html", "template", "build", "generate"]
                found_indicators = sum(1 for indicator in blog_indicators if indicator in content)
                assert found_indicators >= 2, f"Blog generator should contain relevant logic: {file_path}"

    helper.cleanup()


@pytest.mark.asyncio
async def test_password_generator():
    """Test creating a password generator tool."""
    helper = IntegrationTestHelper()
    temp_dir = helper.create_temp_project("password_gen")
    session = await helper.create_session(temp_dir)

    query = "Create a password generator tool that can generate secure passwords with customizable length, character sets (uppercase, lowercase, numbers, symbols)."

    response = await session.process_message(query)
    helper.assert_response_quality(response, ["password", "generator", "random"], min_length=30)

    # Check if password generator files were created
    py_files = list(temp_dir.glob("*.py"))
    if py_files:
        for file_path in py_files:
            content = file_path.read_text().lower()
            # Should contain password generation logic
            pwd_indicators = ["password", "generate", "random", "length", "character"]
            found_indicators = sum(1 for indicator in pwd_indicators if indicator in content)
            assert found_indicators >= 3, f"Password generator should contain generation logic: {file_path}"

    helper.cleanup()