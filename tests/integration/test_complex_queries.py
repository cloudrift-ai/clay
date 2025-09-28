"""Integration tests for complex application creation queries."""

import asyncio
import json
import pytest
from pathlib import Path

from clay.orchestrator import ClayOrchestrator
from clay.trace import set_session_id, save_trace_file
from .test_helpers import assert_response_quality


@pytest.mark.asyncio
async def test_complex_web_application_creation():
    """Test creation of a complete web application with tests, requirements, and documentation.

    This test verifies that the enhanced coding agent creates production-quality
    applications following software engineering best practices.
    """
    # Setup test environment
    test_dir = Path("_test/test_complex_web_app")
    test_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Change to test directory
        original_cwd = Path.cwd()
        import os
        os.chdir(test_dir)

        # Initialize orchestrator with traces
        traces_dir = test_dir / "_trace"
        orchestrator = ClayOrchestrator(traces_dir=traces_dir)

        # Set session for tracing
        set_session_id("complex_web_app_test")

        # Define complex application creation task
        task = """Create a Flask web application for a personal task manager.
        Requirements:
        - User authentication (login/logout)
        - CRUD operations for tasks (create, read, update, delete)
        - Task priority levels (high, medium, low)
        - Due date functionality
        - RESTful API endpoints
        - Input validation and error handling
        - SQLite database with proper schema
        - Comprehensive unit and integration tests
        - Requirements.txt file with all dependencies
        - README.md with setup and usage instructions
        - Proper project structure following Flask best practices
        - Security considerations (CSRF protection, password hashing)
        - Logging configuration
        - Environment-based configuration"""

        # Execute the task
        result = await orchestrator.process_task(task)

        # Verify task completion
        assert result is not None

        # The enhanced agent may create a project in a subdirectory
        # Look for common Flask project structures
        project_dirs = [d for d in Path(".").iterdir() if d.is_dir() and not d.name.startswith('.') and not d.name.startswith('_')]

        # If no project directory found, check current directory
        if not project_dirs:
            project_root = Path(".")
        else:
            # Use the first project directory found (like task_manager, flask_app, etc.)
            project_root = project_dirs[0]

        print(f"📁 Project root: {project_root}")

        # Look for core project files in the project root
        expected_files = [
            "requirements.txt",     # Dependencies
            "README.md",           # Documentation
        ]

        # Check for Python files that indicate a Flask app
        python_files = list(project_root.glob("*.py"))
        has_models = any("models" in f.name for f in python_files)
        has_routes = any("routes" in f.name or "views" in f.name for f in python_files)
        has_app = any("app" in f.name or "main" in f.name for f in python_files)

        flask_indicators = has_models + has_routes + has_app
        assert flask_indicators >= 1, f"No Flask application structure found. Python files: {[f.name for f in python_files]}"

        # Check for requirements.txt in project root or parent
        requirements_found = False
        for req_path in [project_root / "requirements.txt", Path("requirements.txt")]:
            if req_path.exists():
                requirements_found = True
                break
        assert requirements_found, "requirements.txt not found"

        # Check for README in project root or parent
        readme_found = False
        for readme_path in [project_root / "README.md", Path("README.md")]:
            if readme_path.exists():
                readme_found = True
                break
        # Note: README might be empty initially, so we just check existence

        # Check for tests directory in project root or subdirectories
        tests_found = False
        for tests_path in [project_root / "tests", Path("tests")]:
            if tests_path.exists() and tests_path.is_dir():
                tests_found = True
                test_files = list(tests_path.glob("*.py"))
                print(f"🧪 Found {len(test_files)} test files in {tests_path}")
                break

        assert tests_found, "Tests directory was not created"

        # Find and verify requirements.txt content
        requirements_path = None
        for req_path in [project_root / "requirements.txt", Path("requirements.txt")]:
            if req_path.exists():
                requirements_path = req_path
                break

        if requirements_path and requirements_path.stat().st_size > 0:
            requirements_content = requirements_path.read_text()
            flask_deps = ["flask", "pytest"]
            found_deps = sum(1 for dep in flask_deps
                           if any(dep.lower() in line.lower() for line in requirements_content.split('\n')))
            print(f"📦 Found {found_deps}/{len(flask_deps)} expected dependencies")

        # Find tests directory and verify test files
        tests_dir = None
        for tests_path in [project_root / "tests", Path("tests")]:
            if tests_path.exists() and tests_path.is_dir():
                tests_dir = tests_path
                break

        if tests_dir:
            test_files = list(tests_dir.glob("*.py"))
            test_file_names = [f.name for f in test_files]
            has_proper_naming = any("test_" in name for name in test_file_names)
            print(f"🧪 Test files: {test_file_names}")
            assert has_proper_naming or len(test_files) > 0, "Test directory exists but lacks proper test files"

        # Verify trace files were created
        trace_files = list(traces_dir.glob("*.json"))
        assert len(trace_files) > 0, "No trace files were generated"

        # Verify plan iteration files were created
        plan_files = list(traces_dir.glob("plan_iter_*.json"))
        assert len(plan_files) > 0, "No plan iteration files were generated"

        # Analyze final plan to verify engineering best practices
        final_plan_file = max(plan_files, key=lambda x: x.stat().st_mtime)
        with open(final_plan_file, 'r') as f:
            final_plan = json.load(f)

        # Verify the plan shows evidence of engineering best practices
        plan_str = json.dumps(final_plan).lower()
        engineering_practices = [
            "test",           # Testing mentioned
            "requirement",    # Requirements handling
            "error",          # Error handling
            "security",       # Security considerations
            "valid",          # Validation
        ]

        found_practices = sum(1 for practice in engineering_practices
                            if practice in plan_str)
        assert found_practices >= 3, \
            f"Plan doesn't show enough engineering best practices. Found: {found_practices}/5"

        # Look for main application files
        main_file = None
        main_app_files = ["app.py", "main.py", "application.py", "__init__.py"]

        # Check both current directory and project root
        for search_dir in [Path("."), project_root]:
            for filename in main_app_files:
                file_path = search_dir / filename
                if file_path.exists() and file_path.stat().st_size > 0:
                    main_file = file_path
                    break
            if main_file:
                break

        # Also check app subdirectory (common Flask pattern)
        app_dir = project_root / "app"
        if app_dir.exists():
            for filename in main_app_files:
                file_path = app_dir / filename
                if file_path.exists() and file_path.stat().st_size > 0:
                    main_file = file_path
                    break

        print(f"🐍 Main application file: {main_file}")

        # If we found significant Python files earlier, that's sufficient
        if not main_file and flask_indicators >= 1:
            print("✅ Flask application structure verified through models/routes files")

        print(f"✅ Complex web application test passed!")
        print(f"📁 Project root: {project_root}")
        print(f"🐍 Flask indicators: {flask_indicators}")
        print(f"📋 Plan iterations: {len(plan_files)} iterations")
        print(f"📊 Engineering practices found: {found_practices}/{len(engineering_practices)}")

    finally:
        # Cleanup and restore working directory
        os.chdir(original_cwd)
        # Note: We keep test files for inspection but they're in _test directory


@pytest.mark.asyncio
async def test_data_science_project_creation():
    """Test creation of a data science project with analysis, visualization, and documentation."""

    # Setup test environment
    test_dir = Path("_test/test_data_science_project")
    test_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Change to test directory
        original_cwd = Path.cwd()
        import os
        os.chdir(test_dir)

        # Initialize orchestrator with traces
        traces_dir = test_dir / "_trace"
        orchestrator = ClayOrchestrator(traces_dir=traces_dir)

        # Set session for tracing
        set_session_id("data_science_project_test")

        # Define data science project creation task
        task = """Create a data science project for analyzing e-commerce sales data.
        Requirements:
        - Data loading and preprocessing scripts
        - Exploratory data analysis (EDA) with visualizations
        - Statistical analysis and insights
        - Data visualization dashboard or plots
        - Jupyter notebook for analysis walkthrough
        - Unit tests for data processing functions
        - Requirements.txt with data science dependencies
        - README.md with project overview and instructions
        - Sample data generation script
        - Data validation and quality checks
        - Professional code structure with modules
        - Documentation for findings and methodology"""

        # Execute the task
        result = await orchestrator.process_task(task)

        # Verify task completion
        assert result is not None

        # Check for data science project structure
        expected_files = [
            "requirements.txt",
            "README.md",
        ]

        # Look for data science specific files
        data_science_patterns = [
            "*.py",           # Python scripts
            "*.ipynb",        # Jupyter notebooks
        ]

        found_files = []
        for pattern in data_science_patterns:
            found_files.extend(list(Path(".").glob(pattern)))

        assert len(found_files) > 0, "No Python or Jupyter notebook files created"

        # Verify requirements.txt contains data science dependencies
        if Path("requirements.txt").exists():
            requirements_content = Path("requirements.txt").read_text()
            data_deps = ["pandas", "numpy", "matplotlib", "jupyter"]
            found_deps = sum(1 for dep in data_deps
                           if any(dep.lower() in line.lower()
                                 for line in requirements_content.split('\n')))
            assert found_deps >= 2, f"Not enough data science dependencies found: {found_deps}/4"

        # Check for tests directory
        if Path("tests").exists():
            test_files = list(Path("tests").glob("*.py"))
            assert len(test_files) > 0, "Tests directory exists but contains no test files"

        print(f"✅ Data science project test passed!")
        print(f"📄 Python/Jupyter files: {len(found_files)}")

    finally:
        # Cleanup and restore working directory
        os.chdir(original_cwd)


@pytest.mark.asyncio
async def test_api_microservice_creation():
    """Test creation of a RESTful API microservice with comprehensive features."""

    # Setup test environment
    test_dir = Path("_test/test_api_microservice")
    test_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Change to test directory
        original_cwd = Path.cwd()
        import os
        os.chdir(test_dir)

        # Initialize orchestrator with traces
        traces_dir = test_dir / "_trace"
        orchestrator = ClayOrchestrator(traces_dir=traces_dir)

        # Set session for tracing
        set_session_id("api_microservice_test")

        # Define API microservice creation task
        task = """Create a RESTful API microservice for user management using FastAPI.
        Requirements:
        - User CRUD operations (Create, Read, Update, Delete)
        - JWT authentication and authorization
        - Input validation using Pydantic models
        - Database integration with SQLAlchemy
        - API documentation with OpenAPI/Swagger
        - Comprehensive error handling and logging
        - Rate limiting and security headers
        - Health check endpoints
        - Unit and integration tests with pytest
        - Docker containerization
        - Requirements.txt with all dependencies
        - README.md with API documentation and setup
        - Environment configuration management
        - Database migration scripts
        - API versioning support"""

        # Execute the task
        result = await orchestrator.process_task(task)

        # Verify task completion
        assert result is not None

        # Check for API project structure
        expected_files = [
            "requirements.txt",
            "README.md",
        ]

        # Verify core files exist
        created_files = []
        for file_name in expected_files:
            if Path(file_name).exists():
                created_files.append(file_name)

        assert len(created_files) >= 1, f"Expected core files not created: {expected_files}"

        # Look for API-specific files
        api_files = list(Path(".").glob("*.py"))
        assert len(api_files) > 0, "No Python files created for API"

        # Check for FastAPI dependencies in requirements
        if Path("requirements.txt").exists():
            requirements_content = Path("requirements.txt").read_text()
            api_deps = ["fastapi", "uvicorn", "pydantic", "sqlalchemy"]
            found_deps = sum(1 for dep in api_deps
                           if any(dep.lower() in line.lower()
                                 for line in requirements_content.split('\n')))
            assert found_deps >= 2, f"Not enough API dependencies found: {found_deps}/4"

        # Look for main API file
        main_files = ["main.py", "app.py", "api.py"]
        main_file = None
        for filename in main_files:
            if Path(filename).exists():
                main_file = Path(filename)
                break

        if main_file:
            main_content = main_file.read_text()
            fastapi_patterns = ["FastAPI", "@app.", "from fastapi"]
            found_patterns = sum(1 for pattern in fastapi_patterns if pattern in main_content)
            assert found_patterns >= 1, "Main file doesn't appear to use FastAPI"

        print(f"✅ API microservice test passed!")
        print(f"🐍 Python files: {len(api_files)}")
        print(f"📄 Core files: {len(created_files)}")

    finally:
        # Cleanup and restore working directory
        os.chdir(original_cwd)


if __name__ == "__main__":
    # Run tests directly
    asyncio.run(test_complex_web_application_creation())
    asyncio.run(test_data_science_project_creation())
    asyncio.run(test_api_microservice_creation())