"""Bare-minimum orchestrator that just invokes LLM agent."""

from pathlib import Path
from typing import Dict, Any

from ..agents.llm_agent import LLMAgent


class ClayOrchestrator:
    """Minimal orchestrator that just invokes the LLM agent."""

    def __init__(self, agent, working_dir: Path):
        """Initialize the orchestrator with LLM agent."""
        self.working_dir = working_dir
        self.agent = agent

        # Create LLM agent for task processing
        if not hasattr(agent, 'llm_provider') or not agent.llm_provider:
            raise ValueError("Agent must have a valid LLM provider")
        self.llm_agent = LLMAgent(agent.llm_provider)

    async def process_task(self, goal: str) -> Dict[str, Any]:
        """Process a task by directly invoking the LLM agent."""

        if not self.working_dir.exists():
            raise ValueError(f"Working directory {self.working_dir} does not exist")

        try:
            # Generate response using LLM agent
            response = await self.llm_agent.generate_response(
                prompt=goal,
                system_prompt="You are a helpful coding assistant.",
                temperature=0.2
            )

            return {
                "task_id": f"task_{hash(goal) % 10000}",
                "goal": goal,
                "status": "success",
                "response": response,
                "working_dir": str(self.working_dir)
            }

        except Exception as e:
            return {
                "task_id": f"task_{hash(goal) % 10000}",
                "goal": goal,
                "status": "error",
                "error": str(e),
                "working_dir": str(self.working_dir)
            }