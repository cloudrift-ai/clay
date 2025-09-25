# Clay Tests

Comprehensive test suite for the Clay agentic coding system.

## Test Structure

- **`integration/`** - End-to-end tests using ClayOrchestrator directly
- **`tools/`** - Unit tests for individual tools (BashTool, etc.)
- **Test isolation** - Each test runs in isolated `_test/<test_name>/` directory
- **Automatic cleanup** - Test fixtures handle setup and teardown

## Running Tests

### Prerequisites

Ensure you have dependencies installed:
```bash
source venv/bin/activate
pip install -e .
```

### Quick Start

```bash
# Run all tests in parallel (recommended)
source venv/bin/activate && python -m pytest -n auto

# Run all tests with maximum parallelism
source venv/bin/activate && python -m pytest -n 16

# Run specific test module
source venv/bin/activate && python -m pytest tests/tools/test_bash_tool.py -n 16 -v

# Run integration tests only
source venv/bin/activate && python -m pytest tests/integration/ -n 16 -v
```

### Parallel Execution (Recommended)

Clay tests are designed for parallel execution to maximize performance:

```bash
# Use all available CPU cores
python -m pytest -n auto

# Use specific number of processes
python -m pytest -n 16

# Parallel with verbose output
python -m pytest -n 16 -v

# Parallel integration tests only
python -m pytest tests/integration/ -n 16
```

**Performance**: Parallel execution typically runs 4-8x faster than sequential.

### Test Coverage

```bash
# Run with coverage report
python -m pytest --cov=clay --cov-report=html

# Coverage with parallel execution
python -m pytest -n 16 --cov=clay
```

### Development Testing

```bash
# Run specific test
python -m pytest tests/tools/test_bash_tool.py::TestBashTool::test_execute_simple_command -v

# Run tests matching pattern
python -m pytest -k "bash" -v

# Stop on first failure
python -m pytest -x
```

## Test Configuration

Tests automatically:
- Create isolated directories in `_test/<test_name>/`
- Handle cleanup after completion
- Use current working directory as base
- Support async operations with `pytest-asyncio`

## Key Test Features

- **Tool tests**: Validate individual tool functionality (serialization, execution, error handling)
- **Integration tests**: End-to-end ClayOrchestrator workflows
- **Parallel safe**: All tests can run concurrently without conflicts
- **Fast execution**: Optimized for CI/CD pipelines

## Example Output

```bash
$ python -m pytest -n 16 -v
============================= test session starts ==============================
created: 16/16 workers
16 workers [24 items]
...
============================== 24 passed in 2.47s ==============================
```

For more specific test guidance, see individual test files and the project's `CLAUDE.md`.