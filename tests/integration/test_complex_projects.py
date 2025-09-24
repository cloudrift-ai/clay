"""Integration tests for complex multi-step project creation."""

import pytest
from pathlib import Path
from tests.integration.test_helpers import run_clay_command, assert_response_quality


@pytest.mark.slow
@pytest.mark.asyncio
async def test_simple_web_server_project():
    """Test creating a simple web server project."""
    # Create a project subdirectory
    web_server_dir = Path.cwd() / "web_server"
    web_server_dir.mkdir(exist_ok=True)

    query = "Create a simple Python web server project with Flask. Include a main app file, a requirements.txt, and a simple HTML template."

    response = await run_clay_command(query, web_server_dir)
    assert_response_quality(response, ["flask", "server", "app"], min_length=50)

    # Check if project structure was created
    created_files = list(web_server_dir.glob("**/*.py")) + list(web_server_dir.glob("**/*.txt"))
    if created_files:
        # Verify content quality if files were created
        for file_path in created_files:
            assert file_path.stat().st_size > 10, f"File {file_path} is too small"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_calculator_project():
    """Test creating a calculator project."""
    calculator_dir = Path.cwd() / "calculator"
    calculator_dir.mkdir(exist_ok=True)

    query = "Build a command-line calculator application in Python that can perform basic arithmetic operations (add, subtract, multiply, divide) with a menu system."

    response = await run_clay_command(query, calculator_dir)
    assert_response_quality(response, ["calculator", "arithmetic", "menu"], min_length=50)

    # Check for calculator-related files
    py_files = list(calculator_dir.glob("*.py"))
    if py_files:
        for file_path in py_files:
            content = file_path.read_text().lower()
            # Should contain calculator-related functions
            calculator_indicators = ["def", "add", "subtract", "multiply", "divide", "menu", "input"]
            found_indicators = sum(1 for indicator in calculator_indicators if indicator in content)
            assert found_indicators >= 3, f"Calculator file {file_path} should contain calculator logic"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_data_analysis_project():
    """Test creating a data analysis project."""
    data_analysis_dir = Path.cwd() / "data_analysis"
    data_analysis_dir.mkdir(exist_ok=True)

    query = "Create a data analysis project that reads a CSV file, performs basic statistics, and generates visualizations. Include sample data and documentation."

    response = await run_clay_command(query, data_analysis_dir)
    assert_response_quality(response, ["data", "analysis", "csv"], min_length=50)

    # Check for data analysis related files
    created_files = list(data_analysis_dir.glob("**/*"))
    if created_files:
        file_extensions = [f.suffix for f in created_files if f.is_file()]
        # Should have some Python files
        assert any(ext == ".py" for ext in file_extensions), "Should create Python files for analysis"


@pytest.mark.asyncio
async def test_simple_cli_tool():
    """Test creating a simple CLI tool."""
    cli_tool_dir = Path.cwd() / "cli_tool"
    cli_tool_dir.mkdir(exist_ok=True)

    query = "Create a simple command-line tool in Python that counts lines in text files. Include argument parsing and help text."

    response = await run_clay_command(query, cli_tool_dir)
    assert_response_quality(response, min_length=30)

    # Check if any Python files were created
    py_files = list(cli_tool_dir.glob("*.py"))
    if py_files:
        for file_path in py_files:
            content = file_path.read_text().lower()
            # Should contain CLI-related code
            cli_indicators = ["argparse", "main", "if __name__", "def"]
            found_indicators = sum(1 for indicator in cli_indicators if indicator in content)
            assert found_indicators >= 2, f"CLI tool should contain appropriate structure: {file_path}"


@pytest.mark.asyncio
async def test_simple_game():
    """Test creating a simple game."""
    game_dir = Path.cwd() / "game"
    game_dir.mkdir(exist_ok=True)

    query = "Create a simple number guessing game in Python where the computer picks a random number and the user tries to guess it."

    response = await run_clay_command(query, game_dir)
    assert_response_quality(response, ["game", "guess", "number"], min_length=30)

    # Check if game files were created
    py_files = list(game_dir.glob("*.py"))
    if py_files:
        for file_path in py_files:
            content = file_path.read_text().lower()
            # Should contain game-related code
            game_indicators = ["random", "input", "guess", "while", "if"]
            found_indicators = sum(1 for indicator in game_indicators if indicator in content)
            assert found_indicators >= 3, f"Game should contain game logic: {file_path}"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_rest_api_project():
    """Test creating a REST API project."""
    api_dir = Path.cwd() / "api"
    api_dir.mkdir(exist_ok=True)

    query = "Create a simple REST API using Flask with endpoints for CRUD operations on a user resource. Include basic error handling."

    response = await run_clay_command(query, api_dir)
    assert_response_quality(response, ["api", "rest", "flask"], min_length=50)

    # Check if API files were created
    created_files = list(api_dir.glob("**/*.py"))
    if created_files:
        for file_path in created_files:
            content = file_path.read_text().lower()
            # Should contain API-related code
            api_indicators = ["flask", "route", "get", "post", "put", "delete"]
            found_indicators = sum(1 for indicator in api_indicators if indicator in content)
            if found_indicators >= 3:
                # This file contains API logic
                assert "def" in content, f"API file should contain function definitions: {file_path}"


@pytest.mark.asyncio
async def test_utility_library():
    """Test creating a utility library."""
    utils_dir = Path.cwd() / "utils"
    utils_dir.mkdir(exist_ok=True)

    query = "Create a Python utility library with common string manipulation functions: capitalize_words, reverse_string, count_vowels, and remove_whitespace."

    response = await run_clay_command(query, utils_dir)
    assert_response_quality(response, ["utility", "function", "string"], min_length=30)

    # Check if utility files were created
    py_files = list(utils_dir.glob("*.py"))
    if py_files:
        for file_path in py_files:
            content = file_path.read_text().lower()
            # Should contain utility functions
            util_indicators = ["def", "capitalize", "reverse", "count", "remove"]
            found_indicators = sum(1 for indicator in util_indicators if indicator in content)
            assert found_indicators >= 3, f"Utility library should contain multiple functions: {file_path}"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_todo_app_project():
    """Test creating a todo application."""
    todo_app_dir = Path.cwd() / "todo_app"
    todo_app_dir.mkdir(exist_ok=True)

    query = "Create a simple todo application with CLI interface. Users should be able to add, remove, list, and mark tasks as complete. Store tasks in a JSON file."

    response = await run_clay_command(query, todo_app_dir)
    assert_response_quality(response, ["todo", "task", "json"], min_length=50)

    # Check if todo app files were created
    created_files = list(todo_app_dir.glob("**/*"))
    if created_files:
        py_files = [f for f in created_files if f.suffix == ".py"]
        if py_files:
            for file_path in py_files:
                content = file_path.read_text().lower()
                # Should contain todo-related functionality
                todo_indicators = ["add", "remove", "list", "complete", "json", "task"]
                found_indicators = sum(1 for indicator in todo_indicators if indicator in content)
                assert found_indicators >= 3, f"Todo app should contain task management logic: {file_path}"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_blog_generator():
    """Test creating a static blog generator."""
    blog_generator_dir = Path.cwd() / "blog_generator"
    blog_generator_dir.mkdir(exist_ok=True)

    query = "Create a static blog generator in Python that converts Markdown files to HTML. Include template support and a simple build script."

    response = await run_clay_command(query, blog_generator_dir)
    assert_response_quality(response, ["blog", "markdown", "html"], min_length=50)

    # Check if blog generator files were created
    created_files = list(blog_generator_dir.glob("**/*"))
    if created_files:
        py_files = [f for f in created_files if f.suffix == ".py"]
        if py_files:
            for file_path in py_files:
                content = file_path.read_text().lower()
                # Should contain blog generation logic
                blog_indicators = ["markdown", "html", "template", "build", "generate"]
                found_indicators = sum(1 for indicator in blog_indicators if indicator in content)
                assert found_indicators >= 2, f"Blog generator should contain relevant logic: {file_path}"


@pytest.mark.asyncio
async def test_password_generator():
    """Test creating a password generator tool."""
    password_gen_dir = Path.cwd() / "password_gen"
    password_gen_dir.mkdir(exist_ok=True)

    query = "Create a password generator tool that can generate secure passwords with customizable length, character sets (uppercase, lowercase, numbers, symbols)."

    response = await run_clay_command(query, password_gen_dir)
    assert_response_quality(response, ["password", "generator", "random"], min_length=30)

    # Check if password generator files were created
    py_files = list(password_gen_dir.glob("*.py"))
    if py_files:
        for file_path in py_files:
            content = file_path.read_text().lower()
            # Should contain password generation logic
            pwd_indicators = ["password", "generate", "random", "length", "character"]
            found_indicators = sum(1 for indicator in pwd_indicators if indicator in content)
            assert found_indicators >= 3, f"Password generator should contain generation logic: {file_path}"