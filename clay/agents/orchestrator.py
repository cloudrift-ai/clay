"""Agent orchestrator for managing multiple agents."""

import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from .base import Agent, AgentResult, AgentContext


class TaskPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Task:
    """Represents a task for an agent."""
    id: str
    prompt: str
    agent_name: str
    priority: TaskPriority
    dependencies: List[str] = None
    result: Optional[AgentResult] = None


class AgentOrchestrator:
    """Orchestrates multiple agents and manages task execution."""

    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self.tasks: Dict[str, Task] = {}
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.max_concurrent = 3

    def register_agent(self, agent: Agent) -> None:
        """Register an agent with the orchestrator."""
        self.agents[agent.name] = agent

    def create_task(
        self,
        task_id: str,
        prompt: str,
        agent_name: str,
        priority: TaskPriority = TaskPriority.MEDIUM,
        dependencies: Optional[List[str]] = None
    ) -> Task:
        """Create a new task."""
        if agent_name not in self.agents:
            raise ValueError(f"Agent {agent_name} not registered")

        task = Task(
            id=task_id,
            prompt=prompt,
            agent_name=agent_name,
            priority=priority,
            dependencies=dependencies or []
        )
        self.tasks[task_id] = task
        return task

    async def submit_task(self, task: Task) -> None:
        """Submit a task for execution."""
        await self.task_queue.put((task.priority.value, task))

    async def run_task(self, task: Task, context: AgentContext) -> AgentResult:
        """Run a single task."""
        agent = self.agents[task.agent_name]
        result = await agent.run(task.prompt, context)
        task.result = result
        return result

