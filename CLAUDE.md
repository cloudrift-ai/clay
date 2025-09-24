# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development
- **Install dependencies**: `pip install -e .`
- **Run interactive CLI**: `clay chat` or `python -m clay.cli chat`
- **Execute single command**: `clay run "your prompt"` or `python -m clay.cli run "your prompt"`

### Testing
- **Run all tests**: `pytest`
- **Run specific test module**: `pytest tests/test_tools.py`
- **Run with coverage**: `pytest --cov=clay`
- **Run async tests**: Tests use `pytest-asyncio` for async functionality
- **Run tests in parallel**: `pytest -n 4` (using pytest-xdist with 4 workers)
- **Run integration tests in parallel**: `pytest tests/integration/ -n 2` (recommended for integration tests)
- **Test artifacts**: Test files and traces are saved in `_test/<test_name>` for inspection
- **Parallel test isolation**: Each test runs in its own isolated `_test/<test_name>` directory
- **Test setup**: Use `test_helper` fixture from `conftest.py` for test setup (see `_test/MIGRATION.md`)

### Linting and Type Checking
- **Format code**: `black clay/`
- **Lint code**: `ruff check clay/`
- **Type check**: `mypy clay/`

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