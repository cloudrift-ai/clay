"""Coding-focused agent implementation."""

from typing import Dict, Any, List, Optional
import json

from .base import Agent, AgentResult, AgentContext, AgentStatus
from ..llm.base import LLMProvider


class CodingAgent(Agent):
    """Agent specialized for coding tasks."""

    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        super().__init__(
            name="coding_agent",
            description="Agent specialized for writing, editing, and debugging code"
        )
        self.llm_provider = llm_provider

    async def think(self, prompt: str, context: AgentContext) -> AgentResult:
        """Process the prompt and decide on coding actions."""
        if not self.llm_provider:
            return await self._mock_think(prompt, context)

        system_prompt = self._build_system_prompt(context)
        response = await self.llm_provider.complete(
            system_prompt=system_prompt,
            user_prompt=prompt,
            temperature=0.2
        )

        return self._parse_response(response.content)

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

    async def _mock_think(self, prompt: str, context: AgentContext) -> AgentResult:
        """Mock implementation when no LLM provider."""
        prompt_lower = prompt.lower()

        if "read" in prompt_lower and "file" in prompt_lower:
            file_path = self._extract_file_path(prompt)
            if file_path:
                return AgentResult(
                    status=AgentStatus.COMPLETE,
                    output=f"Reading file: {file_path}",
                    tool_calls=[{
                        "name": "read",
                        "parameters": {"file_path": file_path}
                    }]
                )

        elif "write" in prompt_lower or "create" in prompt_lower:
            return AgentResult(
                status=AgentStatus.COMPLETE,
                output="Ready to write file",
                tool_calls=[]
            )

        elif "run" in prompt_lower or "execute" in prompt_lower:
            command = self._extract_command(prompt)
            if command:
                return AgentResult(
                    status=AgentStatus.COMPLETE,
                    output=f"Executing: {command}",
                    tool_calls=[{
                        "name": "bash",
                        "parameters": {"command": command}
                    }]
                )

        return AgentResult(
            status=AgentStatus.COMPLETE,
            output=f"Processing: {prompt}"
        )

    def _extract_file_path(self, prompt: str) -> Optional[str]:
        """Extract file path from prompt."""
        words = prompt.split()
        for i, word in enumerate(words):
            if "/" in word or "." in word:
                return word
        return None

    def _extract_command(self, prompt: str) -> Optional[str]:
        """Extract command from prompt."""
        if "`" in prompt:
            start = prompt.index("`") + 1
            end = prompt.rindex("`")
            return prompt[start:end]
        return None