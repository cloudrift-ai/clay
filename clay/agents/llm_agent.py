"""Generic LLM agent for task analysis and query answering."""

from typing import Dict, Any, List, Optional
import json

from ..llm.base import LLMProvider


class LLMAgent:
    """Generic LLM agent for various AI tasks."""

    def __init__(self, llm_provider: LLMProvider):
        """Initialize the LLM agent."""
        if not llm_provider:
            raise ValueError("LLM provider is required")
        self.llm_provider = llm_provider

    async def analyze_task_complexity(self, prompt: str) -> str:
        """Analyze if a task is simple or complex."""
        response = await self.llm_provider.complete(
            system_prompt="You are a task complexity analyzer. Respond with ONLY 'COMPLEX' or 'SIMPLE' followed by a brief reason (max 20 words).",
            user_prompt=prompt,
            temperature=0.1
        )

        return response.content.strip()

    async def answer_query(self, query: str) -> str:
        """Answer a simple query directly."""
        response = await self.llm_provider.complete(
            system_prompt="You are a helpful assistant. Answer the question or query directly and concisely.",
            user_prompt=query,
            temperature=0.2
        )

        return response.content

    async def create_plan(self, goal: str, context: Dict[str, Any], constraints: Dict[str, Any]) -> Dict[str, Any]:
        """Create a plan for the given goal."""
        prompt = f"""Create a step-by-step plan for: {goal}

Context files available: {len(context.get('files', []))}
Constraints: {constraints}

Respond with a JSON object containing 'steps' (list of strings) and 'description' (string)."""

        response = await self.llm_provider.complete(
            system_prompt="You are a coding planner. Create clear, actionable plans.",
            user_prompt=prompt,
            temperature=0.3
        )

        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"steps": [response.content], "description": "Plan generated"}

    async def propose_patch(self, plan: Dict[str, Any], context: Dict[str, Any], previous_attempts: List[str]) -> str:
        """Propose a patch/diff for the plan or answer simple queries."""
        # Check if this is a simple query (plan has description that's the original goal)
        if plan and plan.get('description') and plan.get('steps') == ["Answer the query directly"]:
            # This is a simple query - just answer it directly
            return await self.answer_query(plan['description'])

        # Complex task - generate code changes
        prompt = f"""Based on this plan, create the necessary code changes:
Plan: {plan}
Previous attempts: {len(previous_attempts)}
Context files: {len(context.get('files', []))}

Generate a unified diff format or return the actual code/response if this is just a query."""

        response = await self.llm_provider.complete(
            system_prompt="You are a code generator. Create precise code changes or answer queries directly.",
            user_prompt=prompt,
            temperature=0.2
        )

        return response.content

    async def suggest_repair(self, failure_context: Dict[str, Any], previous_attempts: List[str], plan: Dict[str, Any]) -> str:
        """Suggest how to repair a failure."""
        prompt = f"""The previous attempt failed. Suggest how to fix:
Failure: {failure_context}
Plan: {plan}
Previous attempts: {len(previous_attempts)}

Provide a concise repair strategy."""

        response = await self.llm_provider.complete(
            system_prompt="You are a debugging assistant. Suggest precise fixes.",
            user_prompt=prompt,
            temperature=0.3
        )

        return response.content

    async def generate_response(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.5) -> str:
        """Generate a generic response for any prompt."""
        response = await self.llm_provider.complete(
            system_prompt=system_prompt or "You are a helpful AI assistant.",
            user_prompt=prompt,
            temperature=temperature
        )

        return response.content