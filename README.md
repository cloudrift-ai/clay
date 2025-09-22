# Clay - Agentic Coding System

An advanced agentic coding system inspired by Claude Code, featuring autonomous code generation, modification, and research capabilities through specialized AI agents.

## Features

- **Multi-Agent Architecture**: Specialized agents for coding and research tasks
- **Tool System**: File operations, bash execution, code search, and web capabilities
- **LLM Integration**: Support for OpenAI GPT and Anthropic Claude models
- **Interactive CLI**: Rich terminal interface with conversation management
- **Extensible Design**: Easy to add new tools and agents

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/clay.git
cd clay

# Install in development mode
pip install -e .
```

## Configuration

Set up your LLM provider API keys:

```bash
# For OpenAI
export OPENAI_API_KEY="your-api-key"

# For Anthropic Claude
export ANTHROPIC_API_KEY="your-api-key"

# For Cloudrift AI
export CLOUDRIFT_API_KEY="your-api-key"
```

## Usage

### Interactive Chat Mode

```bash
# Start interactive session with default provider
clay chat

# Use specific provider
clay chat --provider openai --model gpt-4
clay chat --provider anthropic --model claude-3-5-sonnet-20241022
clay chat --provider cloudrift --model "deepseek-ai/DeepSeek-V3.1"
```

### Single Command Mode

```bash
# Run a single command
clay run "Create a Python script that calculates fibonacci numbers"

# With specific provider
clay run "Search for TODO comments in the codebase" --provider openai
clay run "Create a FastAPI app" --provider cloudrift
```

## Architecture

### Core Components

1. **Tool System** (`clay/tools/`)
   - File operations (read, write, edit, glob)
   - Bash command execution
   - Code search (grep, semantic search)
   - Web tools (fetch, search)

2. **Agent System** (`clay/agents/`)
   - Base agent framework
   - Coding agent for development tasks
   - Research agent for information gathering
   - Agent orchestrator for multi-agent coordination

3. **LLM Integration** (`clay/llm/`)
   - Provider abstraction layer
   - OpenAI GPT support
   - Anthropic Claude support
   - Cloudrift AI support (DeepSeek models)
   - Factory pattern for provider selection

4. **CLI Interface** (`clay/cli.py`)
   - Interactive chat mode
   - Single command execution
   - Rich terminal output

5. **Conversation Management** (`clay/conversation.py`)
   - History tracking
   - Context management
   - Session persistence

## Development

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run all tests
pytest

# Run specific test file
pytest tests/test_tools.py
```

### Project Structure

```
clay/
├── clay/
│   ├── __init__.py
│   ├── cli.py              # CLI interface
│   ├── conversation.py     # Conversation management
│   ├── agents/            # Agent implementations
│   │   ├── base.py
│   │   ├── coding_agent.py
│   │   ├── research_agent.py
│   │   └── orchestrator.py
│   ├── tools/             # Tool implementations
│   │   ├── base.py
│   │   ├── file_tools.py
│   │   ├── bash_tool.py
│   │   ├── search_tools.py
│   │   └── web_tools.py
│   └── llm/               # LLM providers
│       ├── base.py
│       ├── openai_provider.py
│       ├── anthropic_provider.py
│       └── factory.py
├── tests/                 # Test suite
├── pyproject.toml        # Project configuration
└── README.md
```

## Example Commands

```python
# In interactive mode:

clay> Read the file main.py
# Agent reads and displays file content

clay> Search for all TODO comments in Python files
# Research agent searches codebase for TODOs

clay> Create a FastAPI endpoint for user authentication
# Coding agent generates authentication code

clay> Edit config.json to add a new database connection
# Agent modifies existing configuration

clay> Run the test suite
# Agent executes tests using bash tool
```

## Extending Clay

### Adding a New Tool

```python
from clay.tools.base import Tool, ToolResult, ToolStatus

class MyCustomTool(Tool):
    def __init__(self):
        super().__init__(
            name="my_tool",
            description="Does something useful"
        )

    async def execute(self, **kwargs) -> ToolResult:
        # Tool implementation
        return ToolResult(
            status=ToolStatus.SUCCESS,
            output="Tool executed successfully"
        )
```

### Adding a New Agent

```python
from clay.agents.base import Agent, AgentResult

class MyCustomAgent(Agent):
    def __init__(self):
        super().__init__(
            name="custom_agent",
            description="Specialized agent"
        )

    async def think(self, prompt, context):
        # Agent logic
        return AgentResult(
            status=AgentStatus.COMPLETE,
            output="Task completed"
        )
```

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.