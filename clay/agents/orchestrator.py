"""Agent orchestrator for managing multiple agents."""

import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from .base import Agent, AgentResult, AgentContext, AgentStatus


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

    async def process_tasks(self, context: AgentContext) -> None:
        """Process tasks from the queue."""
        while True:
            if len(self.running_tasks) >= self.max_concurrent:
                await asyncio.sleep(0.1)
                continue

            try:
                _, task = await asyncio.wait_for(
                    self.task_queue.get(),
                    timeout=1.0
                )

                if await self._can_run_task(task):
                    task_coro = self.run_task(task, context)
                    self.running_tasks[task.id] = asyncio.create_task(task_coro)
                else:
                    await self.task_queue.put((task.priority.value, task))

            except asyncio.TimeoutError:
                continue

    async def _can_run_task(self, task: Task) -> bool:
        """Check if a task's dependencies are complete."""
        for dep_id in task.dependencies:
            if dep_id not in self.tasks:
                return False
            dep_task = self.tasks[dep_id]
            if dep_task.result is None or dep_task.result.status != AgentStatus.COMPLETE:
                return False
        return True

    async def wait_for_task(self, task_id: str) -> AgentResult:
        """Wait for a task to complete."""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")

        task = self.tasks[task_id]
        while task.result is None:
            await asyncio.sleep(0.1)

        return task.result

    async def wait_all(self) -> Dict[str, AgentResult]:
        """Wait for all tasks to complete."""
        results = {}
        for task_id in self.tasks:
            results[task_id] = await self.wait_for_task(task_id)
        return results