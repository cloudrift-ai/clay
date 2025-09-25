"""Generic LLM agent for task analysis and query answering."""

from typing import Optional

from ..llm import completion


class LLMAgent:
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
        pass

    async def think(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.5) -> str:
        """Think about and respond to a prompt."""
        messages = [
            {"role": "system", "content": system_prompt or "You are a helpful AI assistant."},
            {"role": "user", "content": prompt}
        ]
        response = await completion(messages=messages, temperature=temperature)
        return response['choices'][0]['message']['content']