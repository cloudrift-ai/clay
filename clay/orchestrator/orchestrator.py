"""Clay orchestrator that uses agents to create plans and runtime to execute them."""

from pathlib import Path
from typing import Dict, Any

from ..agents.llm_agent import LLMAgent
from ..agents.coding_agent import CodingAgent
from ..runtime import PlanExecutor, Plan
from ..llm import completion


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

            # Print plan execution start
            plan.print_execution_start()

            if plan.error:
                plan.print_completion()
                return plan  # Return the error plan directly

            # If plan has steps, execute them using the appropriate executor
            if plan.steps:
                plan_executor = self.plan_executors[selected_agent_name]
                execution_result = await plan_executor.execute_plan(plan)
                executed_plan = execution_result["plan"]

                # Print step executions
                for step in executed_plan.steps:
                    executed_plan.print_step_execution(step)

                # Print completion
                executed_plan.print_completion()
                return executed_plan
            else:
                # No plan needed, just return the simple response plan
                plan.print_completion()
                return plan

        except Exception as e:
            error_plan = Plan.create_error_response(
                error=str(e),
                description=f"Orchestrator error processing: {goal[:50]}..."
            )
            error_plan.print_completion()
            return error_plan