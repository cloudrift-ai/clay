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
        """Process a task using agent selection, planning, and runtime execution."""

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

            # Run the selected agent
            plan = await selected_agent.run(goal)

            if plan.error:
                return plan  # Return the error plan directly

            # If plan has steps, execute them step by step
            if plan.steps:
                plan_executor = self.plan_executors[selected_agent_name]

                # Execute steps one by one instead of all at once
                for i, step in enumerate(plan.steps):
                    # Execute the tool for this step
                    tool_name = step.tool_name
                    parameters = step.parameters

                    if tool_name in plan_executor.tools:
                        tool = plan_executor.tools[tool_name]
                        result = await tool.run(**parameters)

                        # Update step result
                        if result.status == ToolStatus.SUCCESS:
                            plan.mark_step_completed(i, result.to_dict())
                        else:
                            error_msg = result.error or "Tool execution failed"
                            plan.mark_step_failed(i, error_msg)
                    else:
                        plan.mark_step_failed(i, f"Tool {tool_name} not found")

                return plan
            else:
                # No plan needed, just return the simple response plan
                return plan

        except Exception as e:
            error_plan = Plan.create_error_response(
                error=str(e),
                description=f"Orchestrator error processing: {goal[:50]}..."
            )
            return error_plan