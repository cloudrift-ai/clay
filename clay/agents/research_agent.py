"""Research-focused agent implementation."""

import json

from .base import Agent, AgentResult, AgentContext, AgentStatus
from ..llm.base import LLMProvider


class ResearchAgent(Agent):
    """Agent specialized for research and information gathering."""

    def __init__(self, llm_provider: LLMProvider):
        super().__init__(
            name="research_agent",
            description="Agent specialized for searching, analyzing, and gathering information"
        )
        if not llm_provider:
            raise ValueError("LLM provider is required")
        self.llm_provider = llm_provider

    async def think(self, prompt: str, context: AgentContext) -> AgentResult:
        """Process the prompt and decide on research actions."""

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

