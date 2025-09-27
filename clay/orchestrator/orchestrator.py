"""Clay orchestrator that uses agents to create plans and runtime to execute them."""

from pathlib import Path
from typing import Dict, Any

from ..agents.llm_agent import LLMAgent
from ..agents.coding_agent import CodingAgent
from ..runtime import PlanExecutor, Plan
from ..llm import completion
from ..tools.base import ToolStatus


class ClayOrchestrator:
    """Orchestrator that coordinates agents and plan execution."""

    def __init__(self):
        """Initialize the orchestrator with all available agents."""
        # Initialize all available agents
        self.agents = {
            'llm_agent': LLMAgent(),
            'coding_agent': CodingAgent()
        }

        # Create plan executors for each agent's tools
        self.plan_executors = {}
        for agent_name, agent in self.agents.items():
            tools = agent.tools if hasattr(agent, 'tools') else {}
            self.plan_executors[agent_name] = PlanExecutor(tools)

    async def select_agent(self, goal: str) -> str:
        """Use LLM to select the best agent for the task."""
        agent_descriptions = self._build_agent_descriptions()
        available_agent_names = list(self.agents.keys())

        system_prompt = f"""You are an agent router that selects the best agent for a given task.

Available agents:
{agent_descriptions}

Choose the most appropriate agent for the task. Respond with ONLY the agent name from: {', '.join(available_agent_names)}.

Selection criteria are automatically derived from each agent's description and capabilities."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Task: {goal}"}
        ]

        response = await completion(messages=messages, temperature=0.1)
        selected_agent = response['choices'][0]['message']['content'].strip().lower()

        # Validate and default to first available agent if unclear
        if selected_agent not in self.agents:
            # Default to first available agent for ambiguous cases
            selected_agent = list(self.agents.keys())[0]

        return selected_agent

    def _build_agent_descriptions(self) -> str:
        """Build a description of available agents."""
        descriptions = []
        for agent_name, agent in self.agents.items():
            description = f"- {agent_name}: {agent.description}"
            if hasattr(agent, 'capabilities'):
                description += f"\n  Capabilities: {', '.join(agent.capabilities)}"
            descriptions.append(description)
        return "\n\n".join(descriptions)

    async def process_task(self, goal: str) -> Plan:
        """Process a task using iterative agent planning and execution.

        The process:
        1. Agent creates initial plan
        2. Execute next step from todo list
        3. Agent reviews plan with completed step and updates todo list
        4. Repeat until todo list is empty
        """

        working_dir = Path.cwd()
        if not working_dir.exists():
            return Plan.create_error_response(
                error=f"Working directory {working_dir} does not exist",
                description="Working directory validation failed"
            )

        try:
            # Select the best agent for the task
            selected_agent_name = await self.select_agent(goal)
            selected_agent = self.agents[selected_agent_name]
            plan_executor = self.plan_executors[selected_agent_name]

            # Get initial plan from agent
            plan = await selected_agent.run(goal)

            # Iterative execution loop
            max_iterations = 50  # Safety limit
            iteration = 0

            while plan.todo and iteration < max_iterations:
                iteration += 1

                # Execute the next step
                next_step = plan.todo[0]
                tool_name = next_step.tool_name
                parameters = next_step.parameters

                if tool_name in plan_executor.tools:
                    tool = plan_executor.tools[tool_name]
                    result = await tool.run(**parameters)

                    # Move step to completed with result
                    if result.status == ToolStatus.SUCCESS:
                        plan.complete_next_step(result=result.to_dict())
                    else:
                        error_msg = result.error or "Tool execution failed"
                        plan.complete_next_step(error=error_msg)
                else:
                    plan.complete_next_step(error=f"Tool {tool_name} not found")

                # Have agent review the plan and update todo list if needed
                if plan.todo:  # Only review if there are more steps
                    plan = await selected_agent.review_plan(plan, goal)

            # Check if we hit the iteration limit
            if iteration >= max_iterations:
                # Add error message to todo list
                from ..runtime.plan import Step
                error_step = Step(
                    tool_name="message",
                    parameters={
                        "message": f"Exceeded maximum iterations ({max_iterations}) while executing plan",
                        "category": "error"
                    },
                    description="Iteration limit exceeded"
                )
                plan.todo.append(error_step)

            return plan

        except Exception as e:
            error_plan = Plan.create_error_response(
                error=str(e),
                description=f"Orchestrator error processing: {goal[:50]}..."
            )
            return error_plan