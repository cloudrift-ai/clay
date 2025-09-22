"""Research-focused agent implementation."""

from typing import Dict, Any, List, Optional
import json

from .base import Agent, AgentResult, AgentContext, AgentStatus
from ..llm.base import LLMProvider


class ResearchAgent(Agent):
    """Agent specialized for research and information gathering."""

    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        super().__init__(
            name="research_agent",
            description="Agent specialized for searching, analyzing, and gathering information"
        )
        self.llm_provider = llm_provider

    async def think(self, prompt: str, context: AgentContext) -> AgentResult:
        """Process the prompt and decide on research actions."""
        if not self.llm_provider:
            return await self._mock_think(prompt, context)

        system_prompt = self._build_system_prompt(context)
        response = await self.llm_provider.complete(
            system_prompt=system_prompt,
            user_prompt=prompt,
            temperature=0.3
        )

        return self._parse_response(response.content)

    def _build_system_prompt(self, context: AgentContext) -> str:
        """Build the system prompt for research tasks."""
        tools_desc = []
        for tool_name, tool in self.tools.items():
            tools_desc.append(f"- {tool_name}: {tool.description}")

        return f"""You are a research assistant focused on information gathering and analysis.

Available tools:
{chr(10).join(tools_desc)}

Working directory: {context.working_directory}

Your task is to:
1. Search for relevant information
2. Analyze findings
3. Provide comprehensive summaries

Respond with JSON:
{{
    "thought": "your analysis",
    "tool_calls": [
        {{
            "name": "tool_name",
            "parameters": {{...}}
        }}
    ],
    "output": "summary of findings"
}}"""

    def _parse_response(self, response: str) -> AgentResult:
        """Parse LLM response."""
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
        """Mock implementation for testing."""
        prompt_lower = prompt.lower()

        if "search" in prompt_lower or "find" in prompt_lower:
            query = self._extract_query(prompt)
            return AgentResult(
                status=AgentStatus.COMPLETE,
                output=f"Searching for: {query}",
                tool_calls=[{
                    "name": "search",
                    "parameters": {"query": query}
                }]
            )

        elif "grep" in prompt_lower:
            pattern = self._extract_pattern(prompt)
            return AgentResult(
                status=AgentStatus.COMPLETE,
                output=f"Searching with pattern: {pattern}",
                tool_calls=[{
                    "name": "grep",
                    "parameters": {"pattern": pattern}
                }]
            )

        elif "web" in prompt_lower or "url" in prompt_lower:
            return AgentResult(
                status=AgentStatus.COMPLETE,
                output="Ready to search the web",
                tool_calls=[]
            )

        return AgentResult(
            status=AgentStatus.COMPLETE,
            output=f"Researching: {prompt}"
        )

    def _extract_query(self, prompt: str) -> str:
        """Extract search query from prompt."""
        keywords = ["search for", "find", "look for"]
        prompt_lower = prompt.lower()

        for keyword in keywords:
            if keyword in prompt_lower:
                start = prompt_lower.index(keyword) + len(keyword)
                return prompt[start:].strip()

        return prompt

    def _extract_pattern(self, prompt: str) -> str:
        """Extract grep pattern from prompt."""
        if '"' in prompt:
            start = prompt.index('"') + 1
            end = prompt.rindex('"')
            return prompt[start:end]
        return prompt.split()[-1]