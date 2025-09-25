"""Generic LLM agent for task analysis and query answering."""

from .base import Agent
from ..llm import completion
from ..runtime import Plan


class LLMAgent(Agent):
    """Generic LLM agent for various AI tasks."""

    name = "llm_agent"
    description = "General-purpose conversational AI agent that can answer questions, provide explanations, help with analysis, and engage in natural language discussions on a wide variety of topics including math, science, programming concepts, and general knowledge."
    capabilities = [
        "Answer factual questions",
        "Provide explanations and tutorials",
        "Help with mathematical calculations",
        "Discuss programming concepts",
        "Analyze and summarize information",
        "Generate creative content",
        "Assist with problem-solving",
        "Engage in general conversation"
    ]

    def __init__(self):
        """Initialize the LLM agent."""
        super().__init__(name=self.name, description=self.description)

    async def think(self, plan: Plan) -> Plan:
        """Think about and respond to a plan."""
        prompt = plan.output or plan.description or "No prompt provided"
        messages = [
            {"role": "system", "content": "You are a helpful AI assistant."},
            {"role": "user", "content": prompt}
        ]
        response = await completion(messages=messages, temperature=0.5)
        return Plan.create_simple_response(
            output=response['choices'][0]['message']['content'],
            description=f"LLM response to: {prompt[:50]}..."
        )