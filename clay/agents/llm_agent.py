"""Generic LLM agent for task analysis and query answering."""

from typing import Dict, Any, List, Optional
import json

from ..llm import completion


class LLMAgent:
    """Generic LLM agent for various AI tasks."""

    def __init__(self, model: str = "deepseek-ai/DeepSeek-V3"):
        """Initialize the LLM agent."""
        self.model = model

    async def analyze_task_complexity(self, prompt: str) -> str:
        """Analyze if a task is simple or complex."""
        messages = [
            {"role": "system", "content": "You are a task complexity analyzer. Respond with ONLY 'COMPLEX' or 'SIMPLE' followed by a brief reason (max 20 words)."},
            {"role": "user", "content": prompt}
        ]
        response = await completion(model=self.model, messages=messages, temperature=0.1)
        return response['choices'][0]['message']['content'].strip()

    async def answer_query(self, query: str) -> str:
        """Answer a simple query directly."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Answer the question or query directly and concisely."},
            {"role": "user", "content": query}
        ]
        response = await completion(model=self.model, messages=messages, temperature=0.2)
        return response['choices'][0]['message']['content']

    async def create_plan(self, goal: str, context: Dict[str, Any], constraints: Dict[str, Any]) -> Dict[str, Any]:
        """Create a plan for the given goal."""
        prompt = f"""Create a step-by-step plan for: {goal}

Context files available: {len(context.get('files', []))}
Constraints: {constraints}

Respond with a JSON object containing 'steps' (list of strings) and 'description' (string)."""

        messages = [
            {"role": "system", "content": "You are a coding planner. Create clear, actionable plans."},
            {"role": "user", "content": prompt}
        ]
        response = await completion(model=self.model, messages=messages, temperature=0.3)

        try:
            return json.loads(response['choices'][0]['message']['content'])
        except json.JSONDecodeError:
            return {"steps": [response['choices'][0]['message']['content']], "description": "Plan generated"}

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

        messages = [
            {"role": "system", "content": "You are a code generator. Create precise code changes or answer queries directly."},
            {"role": "user", "content": prompt}
        ]
        response = await completion(model=self.model, messages=messages, temperature=0.2)
        return response['choices'][0]['message']['content']

    async def suggest_repair(self, failure_context: Dict[str, Any], previous_attempts: List[str], plan: Dict[str, Any]) -> str:
        """Suggest how to repair a failure."""
        prompt = f"""The previous attempt failed. Suggest how to fix:
Failure: {failure_context}
Plan: {plan}
Previous attempts: {len(previous_attempts)}

Provide a concise repair strategy."""

        messages = [
            {"role": "system", "content": "You are a debugging assistant. Suggest precise fixes."},
            {"role": "user", "content": prompt}
        ]
        response = await completion(model=self.model, messages=messages, temperature=0.3)
        return response['choices'][0]['message']['content']

    async def generate_response(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.5) -> str:
        """Generate a generic response for any prompt."""
        messages = [
            {"role": "system", "content": system_prompt or "You are a helpful AI assistant."},
            {"role": "user", "content": prompt}
        ]
        response = await completion(model=self.model, messages=messages, temperature=temperature)
        return response['choices'][0]['message']['content']