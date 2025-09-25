"""Coding-focused agent implementation."""

from typing import Optional
import json

from .base import Agent, AgentResult, AgentContext, AgentStatus
from ..llm import completion


class CodingAgent(Agent):
    """Agent specialized for coding tasks."""

    def __init__(self):
        super().__init__(
            name="coding_agent",
            description="Agent specialized for writing, editing, and debugging code"
        )

    async def think(self, prompt: str, context: AgentContext) -> AgentResult:
        """Process the prompt and decide on coding actions."""
        system_prompt = self._build_system_prompt(context)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        response = await completion(messages=messages, temperature=0.2)
        return self._parse_response(response['choices'][0]['message']['content'])


    def _build_system_prompt(self, context: AgentContext) -> str:
        """Build the system prompt for the LLM."""
        tools_desc = []
        for tool_name, tool in self.tools.items():
            tools_desc.append(f"- {tool_name}: {tool.description}")

        return f"""You are a coding assistant. You MUST use tools to perform actions. Always respond in JSON format.

Available tools:
{chr(10).join(tools_desc)}

Working directory: {context.working_directory}

IMPORTANT: You must actually use tools to perform tasks. Do not just describe what you would do.

For tasks that require creating files, use the 'write' tool.
For tasks that require reading files, use the 'read' tool.
For tasks that require running commands, use the 'bash' tool.

ALWAYS respond with valid JSON in this exact format:

{{
    "thought": "I need to create a Python file, so I'll use the write tool",
    "tool_calls": [
        {{
            "name": "write",
            "parameters": {{
                "file_path": "main.py",
                "content": "def hello_world():\\n    print('Hello, World!')\\n\\nif __name__ == '__main__':\\n    hello_world()"
            }}
        }}
    ],
    "output": "Created main.py with a hello world function"
}}

If no tools are needed for information-only responses:
{{
    "thought": "This is a question that doesn't require tool usage",
    "output": "Here is the information you requested..."
}}"""

    def _parse_response(self, response: str) -> AgentResult:
        """Parse LLM response into AgentResult."""
        # Try to extract JSON from markdown code blocks first
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            if end != -1:
                json_content = response[start:end].strip()
                try:
                    data = json.loads(json_content)
                    return AgentResult(
                        status=AgentStatus.COMPLETE,
                        output=data.get("output", "Task completed"),
                        tool_calls=data.get("tool_calls", [])
                    )
                except json.JSONDecodeError:
                    pass

        # Try to parse as direct JSON
        try:
            data = json.loads(response)
            return AgentResult(
                status=AgentStatus.COMPLETE,
                output=data.get("output", "Task completed"),
                tool_calls=data.get("tool_calls", [])
            )
        except json.JSONDecodeError:
            pass

        # Fallback: return response as output
        return AgentResult(
            status=AgentStatus.COMPLETE,
            output=response
        )

