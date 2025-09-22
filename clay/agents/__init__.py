"""Agent system for Clay."""

from .base import Agent, AgentResult, AgentContext
from .orchestrator import AgentOrchestrator
from .coding_agent import CodingAgent
from .research_agent import ResearchAgent

__all__ = [
    "Agent",
    "AgentResult",
    "AgentContext",
    "AgentOrchestrator",
    "CodingAgent",
    "ResearchAgent",
]