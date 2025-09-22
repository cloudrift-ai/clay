"""Tests for Clay agents."""

import asyncio
import pytest
from pathlib import Path

from clay.agents import (
    CodingAgent, ResearchAgent, AgentOrchestrator,
    AgentContext, AgentStatus, TaskPriority
)
from clay.tools import ReadTool, WriteTool, BashTool, GrepTool


@pytest.fixture
def agent_context():
    """Create a test agent context."""
    return AgentContext(
        working_directory="/tmp",
        conversation_history=[],
        available_tools=[],
        metadata={}
    )


@pytest.mark.asyncio
async def test_coding_agent_basic(agent_context):
    """Test basic coding agent functionality."""
    agent = CodingAgent()
    agent.register_tools([ReadTool(), WriteTool(), BashTool()])

    result = await agent.run(
        prompt="Read the file /etc/hosts",
        context=agent_context
    )

    assert result.status == AgentStatus.COMPLETE
    assert result.output is not None


@pytest.mark.asyncio
async def test_research_agent_basic(agent_context):
    """Test basic research agent functionality."""
    agent = ResearchAgent()
    agent.register_tools([GrepTool()])

    result = await agent.run(
        prompt="Search for TODO comments",
        context=agent_context
    )

    assert result.status == AgentStatus.COMPLETE
    assert result.output is not None


@pytest.mark.asyncio
async def test_agent_orchestrator():
    """Test agent orchestrator."""
    orchestrator = AgentOrchestrator()

    coding_agent = CodingAgent()
    research_agent = ResearchAgent()

    orchestrator.register_agent(coding_agent)
    orchestrator.register_agent(research_agent)

    context = AgentContext(
        working_directory="/tmp",
        conversation_history=[],
        available_tools=[],
        metadata={}
    )

    task1 = orchestrator.create_task(
        task_id="task1",
        prompt="Analyze code structure",
        agent_name="coding_agent",
        priority=TaskPriority.HIGH
    )

    task2 = orchestrator.create_task(
        task_id="task2",
        prompt="Search for patterns",
        agent_name="research_agent",
        priority=TaskPriority.MEDIUM,
        dependencies=["task1"]
    )

    await orchestrator.submit_task(task1)
    await orchestrator.submit_task(task2)

    processor = asyncio.create_task(orchestrator.process_tasks(context))

    result1 = await orchestrator.wait_for_task("task1")
    assert result1.status == AgentStatus.COMPLETE

    result2 = await orchestrator.wait_for_task("task2")
    assert result2.status == AgentStatus.COMPLETE

    processor.cancel()


@pytest.mark.asyncio
async def test_agent_tool_execution(agent_context):
    """Test agent executing tools."""
    agent = CodingAgent()
    bash_tool = BashTool()
    agent.register_tool(bash_tool)

    result = await agent.execute_tool(
        tool_name="bash",
        parameters={"command": "echo 'test'"}
    )

    assert result.status == ToolStatus.SUCCESS
    assert "test" in result.output


@pytest.mark.asyncio
async def test_agent_error_handling(agent_context):
    """Test agent error handling."""
    agent = CodingAgent()

    with pytest.raises(ValueError):
        await agent.execute_tool(
            tool_name="nonexistent",
            parameters={}
        )