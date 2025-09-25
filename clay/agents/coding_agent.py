"""Coding-focused agent implementation."""

from typing import Optional

from .base import Agent
from ..llm import completion
from ..runtime import Plan
from ..tools import BashTool


class CodingAgent(Agent):
    """Agent specialized for coding tasks."""

    name = "coding_agent"
    description = "Specialized agent for software development tasks with access to bash commands for code operations and system tasks."
    capabilities = [
        "Run shell commands and scripts",
        "Execute system operations",
        "Interact with development tools via bash",
        "Perform file operations through command line",
        "Run build, test, and deployment commands"
    ]

    def __init__(self):
        super().__init__(
            name=self.name,
            description=self.description
        )

        # Register essential coding tools
        self.register_tools([
            BashTool()
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

Use the 'bash' tool for all operations including:
- Creating files: echo "content" > file.py
- Reading files: cat file.py
- Editing files: sed commands or text editors
- Running commands: any shell command

ALWAYS respond with valid JSON in this exact format:

{{
    "thought": "I need to create a Python file, so I'll use bash to write the file",
    "plan": [
        {{
            "tool_name": "bash",
            "parameters": {{
                "command": "cat > main.py << 'EOF'\\ndef hello_world():\\n    print('Hello, World!')\\n\\nif __name__ == '__main__':\\n    hello_world()\\nEOF"
            }},
            "description": "Create main.py with hello world function"
        }}
    ],
    "output": "Plan created to create main.py with a hello world function using bash"
}}

If no tools are needed for information-only responses:
{{
    "thought": "This is a question that doesn't require tool usage",
    "output": "Here is the information you requested..."
}}"""


