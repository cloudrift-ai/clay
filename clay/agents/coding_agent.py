"""Coding-focused agent implementation."""

from typing import Optional

from .base import Agent
from ..llm import completion
from ..runtime import Plan
from ..tools import BashTool, MessageTool


class CodingAgent(Agent):
    """Agent specialized for coding tasks."""

    name = "coding_agent"
    description = "Specialized agent for software development tasks with access to bash commands for code operations and system tasks."
    capabilities = [
        "Run shell commands and scripts",
        "Execute system operations",
        "Interact with development tools via bash",
        "Perform file operations through command line",
        "Run build, test, and deployment commands"
    ]

    def __init__(self):
        super().__init__(
            name=self.name,
            description=self.description
        )

        # Register essential coding tools
        self.register_tools([
            BashTool(),
            MessageTool()
        ])

    async def review_plan(self, plan: Plan, task: str) -> Plan:
        """Review current plan state and update todo list based on completed steps."""
        system_prompt = self._build_system_prompt()

        # Distinguish between initial planning and ongoing review
        if not plan.completed and not plan.todo:
            # Initial planning - create first todo list
            user_message = f"""Task: {task}

This is a new task. Create an initial plan with the necessary steps."""
        else:
            # Ongoing review - review current state and update todos
            user_message = f"""Task: {task}

Current plan state:
{plan.to_json()}

Based on the completed steps and their results, provide an updated todo list.
If the task is complete, return an empty todo list with the final output.
If more steps are needed, specify them in the todo list."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        response = await completion(messages=messages, temperature=0.2)
        response_text = response['choices'][0]['message']['content']

        # Parse the response and update the plan
        new_plan = Plan.from_response(response_text)

        # Preserve completed steps
        new_plan.completed = plan.completed

        # Update todo list from agent's response
        if hasattr(new_plan, 'todo') and new_plan.todo:
            plan.todo = new_plan.todo
        else:
            plan.todo = []

        return plan


    def _build_system_prompt(self) -> str:
        """Build the system prompt for the agent."""
        tools_desc = self.get_tools_description(include_capabilities=True, include_use_cases=True, include_schema=True)
        json_format = self.get_json_format_instructions()

        return f"""You are a coding assistant that creates and reviews execution plans.

For new tasks, create an initial plan with necessary steps.
For ongoing tasks, review completed steps and update the todo list.

You will receive:
1. The original task
2. A list of completed steps and their results (if any)
3. The current todo list (if any)

Your job is to:
1. For new tasks: Create an initial todo list
2. For ongoing tasks: Review results and update the todo list
3. Determine if the task is complete or if more steps are needed
4. If the task is complete, provide the final output

Available tools:
{tools_desc}

{json_format}

IMPORTANT:
- You must create concrete steps with tools to perform tasks
- Don't just describe what you would do - specify the actual commands/tools
- Review the results carefully to determine next steps
- If a step failed, you may need to add corrective steps
- If the task is complete, return an empty todo list
- Always provide clear output describing what was accomplished"""


