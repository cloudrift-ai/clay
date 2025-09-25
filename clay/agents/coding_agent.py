"""Coding-focused agent implementation."""

from typing import Optional

from .base import Agent
from ..llm import completion
from ..runtime import Plan
from ..tools import (
    ReadTool, WriteTool, EditTool, GlobTool,
    BashTool, GrepTool, SearchTool
)


class CodingAgent(Agent):
    """Agent specialized for coding tasks."""

    name = "coding_agent"
    description = "Specialized agent for software development tasks including writing, editing, debugging, and analyzing code. Can work with multiple programming languages and has access to file system tools for reading, writing, and modifying code files."
    capabilities = [
        "Write new code files and functions",
        "Edit existing code files",
        "Debug and fix code issues",
        "Read and analyze code files",
        "Search through codebases",
        "Run shell commands and scripts",
        "Create and modify file structures",
        "Generate code documentation",
        "Perform code refactoring",
        "Execute file operations (glob, grep, etc.)"
    ]

    def __init__(self):
        super().__init__(
            name=self.name,
            description=self.description
        )

        # Register essential coding tools
        self.register_tools([
            ReadTool(),
            WriteTool(),
            EditTool(),
            GlobTool(),
            BashTool(),
            GrepTool(),
            SearchTool()
        ])

    async def think(self, plan: Plan) -> Plan:
        """Process the plan and decide on coding actions."""
        system_prompt = self._build_system_prompt()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": plan.output or plan.description or "No prompt provided"}
        ]
        response = await completion(messages=messages, temperature=0.2)
        return Plan.from_response(response['choices'][0]['message']['content'])


    def _build_system_prompt(self) -> str:
        """Build the system prompt for the LLM."""
        tools_desc = self.get_tools_description()

        return f"""You are a coding assistant. You create execution plans with tools to perform actions. Always respond in JSON format.

Available tools:
{tools_desc}

IMPORTANT: You must create a plan with tools to perform tasks. Do not just describe what you would do.

For tasks that require creating files, use the 'write' tool.
For tasks that require reading files, use the 'read' tool.
For tasks that require running commands, use the 'bash' tool.

ALWAYS respond with valid JSON in this exact format:

{{
    "thought": "I need to create a Python file, so I'll plan to use the write tool",
    "plan": [
        {{
            "tool_name": "write",
            "parameters": {{
                "file_path": "main.py",
                "content": "def hello_world():\\n    print('Hello, World!')\\n\\nif __name__ == '__main__':\\n    hello_world()"
            }},
            "description": "Create main.py with hello world function"
        }}
    ],
    "output": "Plan created to create main.py with a hello world function"
}}

If no tools are needed for information-only responses:
{{
    "thought": "This is a question that doesn't require tool usage",
    "output": "Here is the information you requested..."
}}"""


