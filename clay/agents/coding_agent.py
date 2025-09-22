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

        return f"""You are a coding assistant with access to these tools:
{chr(10).join(tools_desc)}

Working directory: {context.working_directory}

When you need to use a tool, respond with JSON in this format:
{{
    "thought": "your reasoning",
    "tool_calls": [
        {{
            "name": "tool_name",
            "parameters": {{...}}
        }}
    ],
    "output": "explanation of what you're doing"
}}

If no tools are needed, respond with:
{{
    "thought": "your reasoning",
    "output": "your response"
}}"""

    def _parse_response(self, response: str) -> AgentResult:
        """Parse LLM response into AgentResult."""
        try:
            data = json.loads(response)
            return AgentResult(
                status=AgentStatus.COMPLETE,
                output=data.get("output"),
                tool_calls=data.get("tool_calls", [])
            )
        except json.JSONDecodeError:
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