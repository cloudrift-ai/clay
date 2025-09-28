"""Clay orchestrator that uses agents to create plans and runtime to execute them."""

from pathlib import Path
from typing import Dict, Any, Optional
import json
from datetime import datetime

from ..agents.llm_agent import LLMAgent
from ..agents.coding_agent import CodingAgent
from ..runtime import Plan
from ..llm import completion
from ..tools.base import ToolStatus
from ..trace import trace_operation, clear_trace, save_trace_file, set_session_id


class ClayOrchestrator:
    """Orchestrator that coordinates agents and plan execution."""

    def __init__(self, traces_dir: Optional[Path] = None):
        """Initialize the orchestrator with all available agents.

        Args:
            traces_dir: Directory to save traces and plan files. If None, uses current directory's _trace/
        """
        # Initialize all available agents
        self.agents = {
            'llm_agent': LLMAgent(),
            'coding_agent': CodingAgent()
        }

        # Create tool registries for each agent
        self.agent_tools = {}
        for agent_name, agent in self.agents.items():
            self.agent_tools[agent_name] = agent.tools if hasattr(agent, 'tools') else {}

        # Set traces directory
        self.traces_dir = traces_dir

    @trace_operation
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

    def _save_plan_to_trace_dir(self, plan: Plan, iteration: int, goal: str) -> Path:
        """Save the plan to the traces directory for debugging."""
        # Use configured traces directory or default to current directory's _trace
        if self.traces_dir:
            trace_dir = self.traces_dir
        else:
            trace_dir = Path.cwd() / "_trace"
        trace_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp and iteration
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"plan_iter_{iteration:03d}_{timestamp}.json"
        filepath = trace_dir / filename

        # Create plan data with metadata
        plan_data = {
            "iteration": iteration,
            "timestamp": datetime.now().isoformat(),
            "goal": goal,
            "plan": plan.to_dict()
        }

        # Save to file
        with open(filepath, 'w') as f:
            json.dump(plan_data, f, indent=2)

        return filepath

    def _build_agent_descriptions(self) -> str:
        """Build a description of available agents."""
        descriptions = []
        for agent_name, agent in self.agents.items():
            description = f"- {agent_name}: {agent.description}"
            if hasattr(agent, 'capabilities'):
                description += f"\n  Capabilities: {', '.join(agent.capabilities)}"
            descriptions.append(description)
        return "\n\n".join(descriptions)

    @trace_operation
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
            # Set up tracing if traces directory is configured
            session_id = None
            if self.traces_dir:
                # Clear previous traces and set up new session
                clear_trace()
                session_id = f"orchestrator_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                set_session_id(session_id)

            # Select the best agent for the task
            selected_agent_name = await self.select_agent(goal)
            selected_agent = self.agents[selected_agent_name]
            agent_tools = self.agent_tools[selected_agent_name]

            # Get initial plan from agent
            plan = await selected_agent.run(goal)

            # Save initial plan (iteration 0)
            self._save_plan_to_trace_dir(plan, 0, goal)

            # Iterative execution loop
            max_iterations = 50  # Safety limit
            iteration = 0

            while plan.todo and iteration < max_iterations:
                iteration += 1

                # Execute the next step
                next_step = plan.todo[0]
                tool_name = next_step.tool_name
                parameters = next_step.parameters

                if tool_name in agent_tools:
                    tool = agent_tools[tool_name]
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

                # Save plan after each iteration
                self._save_plan_to_trace_dir(plan, iteration, goal)

                # Save trace after each iteration (overwrites same file for real-time updates)
                if self.traces_dir and session_id:
                    save_trace_file(session_id, self.traces_dir)

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
            # Save error trace if traces directory is configured
            if self.traces_dir and session_id:
                save_trace_file(f"{session_id}_error", self.traces_dir)

            error_plan = Plan.create_error_response(
                error=str(e),
                description=f"Orchestrator error processing: {goal[:50]}..."
            )
            return error_plan