# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**IMPORTANT: Always use the virtual environment for all commands below.**

### Environment Setup
- **Activate virtual environment**: `source venv/bin/activate` (must be done before any other commands)
- **Install dependencies**: `source venv/bin/activate && pip install -e .`

### Development
- **Run interactive CLI**: `source venv/bin/activate && clay chat` or `source venv/bin/activate && python -m clay.cli chat`
- **Execute single command**: `source venv/bin/activate && clay run "your prompt"` or `source venv/bin/activate && python -m clay.cli run "your prompt"`

### Testing
- **Run all tests**: `source venv/bin/activate && python -m pytest`
- **Run specific test module**: `source venv/bin/activate && python -m pytest tests/test_trace.py`
- **Run with coverage**: `source venv/bin/activate && python -m pytest --cov=clay`
- **Run async tests**: Tests use `pytest-asyncio` for async functionality
- **Run tests in parallel**: `source venv/bin/activate && python -m pytest -n 16` (using pytest-xdist with 16 workers)
- **Run integration tests in parallel**: `source venv/bin/activate && python -m pytest tests/integration/ -n 16` (recommended for integration tests)
- **Test artifacts**: Test files and traces are saved in `_test/<test_name>` for inspection
- **Parallel test isolation**: Each test runs in its own isolated `_test/<test_name>` directory
- **Test setup**: Automatic cleanup fixtures in `conftest.py` handle test isolation

### Linting and Type Checking
- **Format code**: `source venv/bin/activate && black clay/`
- **Lint code**: `source venv/bin/activate && ruff check clay/`
- **Type check**: `source venv/bin/activate && mypy clay/`

### Tracing and Analysis
- **Enable tracing**: Use `@trace_operation("Component", "operation_name")` decorator on functions
- **Method tracing**: Use `@trace_method()` decorator on class methods (auto-detects component name)
- **Trace Clay execution**: All Clay CLI commands automatically generate traces in `traces/` directory
- **Trace test runs**: All pytest executions automatically save traces to `_test/<test_name>/traces/`
- **View trace files**: Check `traces/` directory for JSON files with complete execution trees
- **Analyze program behavior**: Trace files show nested call hierarchies, timing, arguments, and errors
- **Test tracing system**: `source venv/bin/activate && python -m pytest tests/test_trace.py` (31 comprehensive tests)
- **Session management**: Use `set_session_id("session_name")` and `save_trace_file()` for organized traces

**How to Use Tracing for Debugging:**
```bash
# Run Clay with automatic tracing enabled
source venv/bin/activate && python -m clay.cli run "your command"
# Traces automatically saved to traces/clay_trace_TIMESTAMP_SESSION.json

# Run tests with automatic tracing
source venv/bin/activate && python -m pytest tests/integration/test_coding_tasks.py
# Traces saved to _test/test_*/traces/ for each test

# Analyze specific trace file
jq '.call_stack[] | {component, operation, duration}' traces/clay_trace_latest.json
```

## Architecture Overview

Clay is an agentic coding system with a modular architecture:

### Multi-Agent System
- **Agent Orchestrator** (`clay/agents/orchestrator.py`): Manages multiple agents, handles task dependencies and priority scheduling
- **Coding Agent**: Specializes in code generation, file operations, and development tasks
- **Research Agent**: Focuses on information gathering, searching, and analysis
- Agents communicate through a shared context and can be extended with custom implementations

### Tool System
- Tools inherit from `Tool` base class and implement `execute()` method
- Each tool returns `ToolResult` with status, output, and metadata
- Tools are registered with agents and executed asynchronously
- File operations maintain exact whitespace and indentation preservation

### LLM Integration
- Provider abstraction supports multiple LLM backends (OpenAI, Anthropic, Cloudrift)
- Factory pattern for provider selection based on available API keys
- Streaming support for real-time response generation
- Context window management for conversation history
- Cloudrift provider supports DeepSeek models and other models from https://inference.cloudrift.ai/v1/models

### Conversation Management
- Maintains conversation history with role-based messages
- Automatic context window trimming to stay within limits
- Session persistence for saving/loading conversations
- Metadata support for tracking tool usage and agent decisions

### Tracing System
- **Comprehensive execution tracing** with nested call stack reproduction
- **Automatic tracing** for all Clay CLI commands and test executions
- **Thread-safe** concurrent execution support
- **Decorator-based tracing** using `@trace_operation()` and `@trace_method()`
- **Automatic context capture**: file paths, line numbers, function names, and simple argument values
- **JSON output** with hierarchical structure showing complete call trees
- **Error handling** with full stack traces preserved in nested structure
- **Performance timing** with precise duration measurements for each function call
- **Organized trace storage**: CLI traces in `traces/`, test traces in `_test/<test_name>/traces/`
- **Production-ready monitoring** for debugging complex multi-agent interactions

## Tracing System Usage

Use Clay's tracing system to analyze program behavior, debug execution flow, and monitor performance.

### Basic Usage
```python
from clay.trace import trace_operation, trace_method, save_trace_file, set_session_id

@trace_operation("Calculator", "add")
def add_numbers(a: int, b: int) -> int:
    return a + b

class DataProcessor:
    @trace_method()  # Auto-detects component as "DataProcessor"
    def process(self, data: list) -> list:
        return [self.transform(item) for item in data]

    @trace_method()
    def transform(self, item):
        return item.upper()

# Usage with session management
set_session_id("analysis_session")
result = add_numbers(10, 20)
processor = DataProcessor()
processed = processor.process(["hello", "world"])
trace_file = save_trace_file()  # Saves to traces/ directory
```

### Key Features
- **Nested calls**: Functions calling other traced functions create hierarchical trace trees
- **Error tracking**: Exceptions are captured with full stack traces in the nested structure
- **Thread safety**: Multiple threads can trace concurrently without interference
- **Argument capture**: Simple argument values (strings, numbers, small collections) are recorded
- **Performance timing**: Precise duration measurements for each function call

### Trace File Contents
JSON files in `traces/` contain:
- **Call hierarchy**: Complete tree showing which functions called which
- **Context information**: File paths, line numbers, function names for each call
- **Arguments**: Captured argument values and counts (simple types only)
- **Timing**: Duration in seconds for performance analysis
- **Errors**: Exception messages and stack traces when errors occur
- **Threading**: Thread IDs for concurrent execution analysis

### When to Use Tracing
- **Debugging complex flows** where multiple components interact
- **Performance analysis** to identify bottlenecks and slow operations
- **System monitoring** to understand behavior in multi-agent scenarios
- **Testing validation** to verify correct execution sequences
- **Production analysis** to track errors and system behavior patterns

### Automatic Tracing in Clay

**Every Clay execution is automatically traced:**
- **CLI commands**: `python -m clay.cli run "command"` → traces saved to `traces/`
- **Interactive sessions**: `python -m clay.cli chat` → traces saved with session IDs
- **Test execution**: All pytest runs save traces to `_test/<test_name>/traces/`
- **Integration tests**: Each test gets its own isolated trace directory

**Common Debugging Workflows:**

1. **Debug failing Clay command**:
   ```bash
   # Run the failing command
   source venv/bin/activate && python -m clay.cli run "problematic command"

   # Find the latest trace
   ls -la traces/ | tail -1

   # Analyze execution flow
   jq '.call_stack[] | select(.error != null)' traces/latest_trace.json
   ```

2. **Debug slow performance**:
   ```bash
   # Check execution timing
   jq '.call_stack[] | {component, operation, duration} | select(.duration > 1)' traces/trace.json

   # Find LLM call performance
   jq '.call_stack[] | .. | select(.component? == "LLM") | {operation, duration, details}' traces/trace.json
   ```

3. **Debug test failures**:
   ```bash
   # Run failing test
   source venv/bin/activate && python -m pytest tests/integration/test_coding_tasks.py::test_name -v

   # Check test trace
   find _test -name "*.json" -exec jq '.call_stack[] | select(.error != null)' {} \;
   ```