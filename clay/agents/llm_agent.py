"""Generic LLM agent for task analysis and query answering."""

from .base import Agent
from ..llm import completion
from ..runtime import Plan
from ..tools import MessageTool


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

        # Register message tool for communication
        self.register_tools([
            MessageTool()
        ])

    async def review_plan(self, plan: Plan, task: str) -> Plan:
        """Review current plan state and update todo list.

        For LLM agent, we typically don't need tools, so just provide a response.
        """
        # If plan has no todos and has a message step in completed, return as-is
        has_message_step = any(step.tool_name == "message" for step in plan.completed)
        if not plan.todo and has_message_step:
            return plan

        # Generate a response for the task (both initial and review cases)
        if plan.completed:
            # This is a review - we have completed steps
            user_message = f"""Task: {task}

Current plan state:
{plan.to_json()}

Based on the current state, provide a final response or continue with more steps."""
        else:
            # This is initial planning
            user_message = task

        messages = [
            {"role": "system", "content": "You are a helpful AI assistant. Provide clear, concise answers. For most tasks, you don't need tools - just provide the information directly."},
            {"role": "user", "content": user_message}
        ]

        response = await completion(messages=messages, temperature=0.5)

        # Create a message step with the response
        from ..runtime import Step
        message_step = Step(
            tool_name="message",
            parameters={
                "message": response['choices'][0]['message']['content'],
                "category": "info"
            },
            description=f"LLM response to: {task[:50]}..."
        )

        plan.todo = [message_step]
        plan.description = f"LLM response to: {task[:50]}..."

        return plan