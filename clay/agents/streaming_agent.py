"""Streaming agent that provides real-time progress feedback."""

import asyncio
from typing import Dict, Any, List, Optional, AsyncGenerator
from enum import Enum

from .base import Agent, AgentResult, AgentContext, AgentStatus
from ..llm.base import LLMProvider


class ProgressPhase(Enum):
    ANALYZING = "analyzing"
    PLANNING = "planning"
    EXECUTING = "executing"
    VALIDATING = "validating"
    COMPLETE = "complete"


class ProgressUpdate:
    def __init__(self, phase: ProgressPhase, message: str, progress: float = 0.0):
        self.phase = phase
        self.message = message
        self.progress = progress  # 0.0 to 1.0


class StreamingAgent(Agent):
    """Agent that provides real-time progress updates during execution."""

    def __init__(self, base_agent: Agent):
        super().__init__(
            name=f"streaming_{base_agent.name}",
            description=f"Streaming version of {base_agent.description}"
        )
        self.base_agent = base_agent
        self.tools = base_agent.tools
        self.llm_provider = getattr(base_agent, 'llm_provider', None)

    async def think(self, prompt: str, context: AgentContext) -> AgentResult:
        """Think method that doesn't provide streaming - use stream_think instead."""
        return await self.base_agent.think(prompt, context)

    async def stream_think(self, prompt: str, context: AgentContext) -> AsyncGenerator[ProgressUpdate, AgentResult]:
        """Stream progress updates while thinking."""
        # Phase 1: Analyzing
        yield ProgressUpdate(ProgressPhase.ANALYZING, "🔍 Analyzing task requirements...", 0.1)
        await asyncio.sleep(0.5)  # Allow UI to update

        # Phase 2: Planning
        yield ProgressUpdate(ProgressPhase.PLANNING, "📋 Creating execution plan...", 0.3)

        if self.llm_provider:
            # Get plan from LLM
            planning_prompt = f"""
            Analyze this task and create a brief execution plan:
            Task: {prompt}

            Provide a concise plan with 3-5 steps.
            """
            try:
                plan_response = await self.llm_provider.complete(
                    system_prompt="You are a planning assistant. Provide concise, actionable plans.",
                    user_prompt=planning_prompt,
                    temperature=0.2,
                    max_tokens=500
                )
                plan = plan_response.content[:200] + "..." if len(plan_response.content) > 200 else plan_response.content
                yield ProgressUpdate(ProgressPhase.PLANNING, f"📋 Plan ready: {plan}", 0.5)
            except Exception:
                yield ProgressUpdate(ProgressPhase.PLANNING, "📋 Plan created", 0.5)
        else:
            yield ProgressUpdate(ProgressPhase.PLANNING, "📋 Plan created", 0.5)

        await asyncio.sleep(0.3)

        # Phase 3: Executing
        yield ProgressUpdate(ProgressPhase.EXECUTING, "🔧 Executing task...", 0.7)

        # Execute the actual task
        result = await self.base_agent.think(prompt, context)

        if result.tool_calls:
            yield ProgressUpdate(ProgressPhase.EXECUTING, f"🔧 Running {len(result.tool_calls)} tool(s)...", 0.8)

        await asyncio.sleep(0.2)

        # Phase 4: Validating
        yield ProgressUpdate(ProgressPhase.VALIDATING, "✅ Validating results...", 0.9)
        await asyncio.sleep(0.3)

        # Phase 5: Complete
        yield ProgressUpdate(ProgressPhase.COMPLETE, "🎉 Task completed!", 1.0)

        # Final result as special update containing the result
        final_update = ProgressUpdate(ProgressPhase.COMPLETE, "Task completed", 1.0)
        final_update.result = result
        yield final_update

    async def run_with_progress(self, prompt: str, context: AgentContext) -> AsyncGenerator[ProgressUpdate, AgentResult]:
        """Run agent with progress updates and tool execution."""
        self.context = context
        self.status = AgentStatus.THINKING

        try:
            # Stream the thinking process
            async for update in self.stream_think(prompt, context):
                yield update

                # If we get the final result, process tool calls
                if isinstance(update, AgentResult):
                    result = update

                    if result.tool_calls:
                        self.status = AgentStatus.RUNNING_TOOL
                        tool_results = []

                        for i, call in enumerate(result.tool_calls):
                            yield ProgressUpdate(
                                ProgressPhase.EXECUTING,
                                f"🔧 Executing {call['name']} ({i+1}/{len(result.tool_calls)})...",
                                0.8 + (i / len(result.tool_calls)) * 0.1
                            )

                            tool_result = await self.execute_tool(
                                call["name"],
                                call["parameters"]
                            )
                            tool_results.append({
                                "tool": call["name"],
                                "result": tool_result.to_dict()
                            })

                        result.metadata = {"tool_results": tool_results}

                    self.status = AgentStatus.COMPLETE
                    final_update = ProgressUpdate(ProgressPhase.COMPLETE, "Task completed", 1.0)
                    final_update.result = result
                    yield final_update

        except Exception as e:
            self.status = AgentStatus.ERROR
            error_update = ProgressUpdate(ProgressPhase.COMPLETE, f"❌ Error: {str(e)}", 1.0)
            error_update.result = AgentResult(
                status=AgentStatus.ERROR,
                error=str(e)
            )
            yield error_update


class ProgressiveSession:
    """Session that provides progress feedback for long operations."""

    def __init__(self, base_session):
        self.base_session = base_session

    async def process_with_progress(self, message: str, progress_callback=None):
        """Process message with progress callbacks."""
        # Wrap the agent in a streaming agent
        if hasattr(self.base_session, 'orchestrator'):
            # For complex sessions with orchestrator
            return await self._process_complex_with_progress(message, progress_callback)
        else:
            # For simple sessions
            return await self._process_simple_with_progress(message, progress_callback)

    async def _process_simple_with_progress(self, message: str, progress_callback=None):
        """Process simple message with progress."""
        if progress_callback:
            progress_callback("🤔 Starting analysis...")

        result = await self.base_session.process_message(message)

        if progress_callback:
            progress_callback("✅ Complete!")

        return result

    async def _process_complex_with_progress(self, message: str, progress_callback=None):
        """Process complex message with detailed progress."""
        phases = [
            "🤔 Analyzing request...",
            "🎯 Selecting appropriate agent...",
            "📋 Planning approach...",
            "🔧 Executing tools...",
            "✅ Finalizing results..."
        ]

        if progress_callback:
            for i, phase in enumerate(phases[:-1]):
                progress_callback(phase)
                await asyncio.sleep(0.2)  # Allow UI updates

        result = await self.base_session.process_message(message)

        if progress_callback:
            progress_callback(phases[-1])

        return result