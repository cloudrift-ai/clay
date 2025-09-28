"""Generic LLM agent for task analysis and query answering."""

from .base import Agent
from ..llm import completion
from ..orchestrator import Plan, Step
from ..tools import AgentMessageTool, UserMessageTool
from ..trace import trace_operation


class LLMAgent(Agent):
    """Generic LLM agent for various AI tasks."""

    name = "llm_agent"
    description = "General-purpose conversational AI agent that provides information and answers questions. Does NOT execute files, commands, or perform actual coding tasks. Can answer questions, provide explanations, help with analysis, and engage in natural language discussions on a wide variety of topics including math, science, programming concepts, and general knowledge."
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

        # Register communication tools
        self.register_tools([
            AgentMessageTool(),
            UserMessageTool()
        ])

    @trace_operation
    async def review_plan(self, plan: Plan) -> Plan:
        """Review current plan state and update todo list.

        For LLM agent, we typically don't need tools, so just provide a response.
        The user's intent is communicated through UserMessageTool in plan.completed.
        """
        # If plan has no todos and has a message step in completed, return as-is
        has_message_step = any(step.tool_name == "message" for step in plan.completed)
        if not plan.todo and has_message_step:
            return plan

        # Extract user intent from UserMessageTool
        user_message_steps = [step for step in plan.completed if step.tool_name == "user_message"]
        if not user_message_steps:
            # Fallback for edge cases
            task = "Please provide assistance"
        else:
            task = user_message_steps[0].parameters.get("message", "Please provide assistance")

        # Generate a response for the task (both initial and review cases)
        if len(plan.completed) > 1:  # More than just UserMessageTool
            # This is a review - we have completed steps beyond UserMessageTool
            user_message = f"""Current plan state:
{plan.to_json()}

Based on the current state, provide a final response or continue with more steps.
The user's original request is in the UserMessageTool."""
        else:
            # This is initial planning - only UserMessageTool present
            user_message = f"""The user has requested: {task}

Provide a helpful response. For most tasks, you don't need tools - just provide the information directly."""

        messages = [
            {"role": "system", "content": "You are a helpful AI assistant. The user's intent is communicated through UserMessageTool in the plan. Provide clear, concise answers. For most tasks, you don't need tools - just provide the information directly."},
            {"role": "user", "content": user_message}
        ]

        response = await completion(messages=messages, temperature=0.5)

        # Create a message step with the response
        message_step = Step(
            tool_name="message",
            parameters={
                "message": response['choices'][0]['message']['content'],
                "category": "info"
            },
            description=f"LLM response to: {task[:50]}..."
        )

        plan.todo = [message_step]

        return plan