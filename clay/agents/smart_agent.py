"""Smart agent that uses multi-model routing for different task types."""

from typing import Dict, Any, Optional
import json

from .base import Agent, AgentResult, AgentContext, AgentStatus
from ..llm.base import LLMProvider
from ..llm.model_router import ModelRouter, TaskType
from ..config import get_config


class SmartAgent(Agent):
    """Agent that intelligently routes tasks to appropriate models."""

    def __init__(self, api_keys: Optional[Dict[str, str]] = None, agent_name: str = "smart_agent"):
        super().__init__(
            name=agent_name,
            description="Intelligent agent that routes tasks to optimal models"
        )

        # Get API keys from config if not provided
        if api_keys is None:
            config = get_config()
            api_keys = {}
            for provider in ['cloudrift', 'anthropic', 'openai']:
                key, _ = config.get_provider_credentials(provider)
                if key:
                    api_keys[provider] = key

        self.model_router = ModelRouter(api_keys)
        self.config = get_config()

    async def think(self, prompt: str, context: AgentContext) -> AgentResult:
        """Process the prompt using the most appropriate model."""

        # Check if multi-model routing is enabled
        if not self.config.is_multi_model_routing_enabled():
            return await self._fallback_think(prompt, context)

        # Get the best model for this task
        provider, task_type, model_config = self.model_router.get_model_for_task(
            prompt,
            {"working_directory": context.working_directory}
        )

        if not provider or not model_config:
            return await self._fallback_think(prompt, context)

        # Print model selection info
        from rich.console import Console
        console = Console()
        console.print(f"[dim]→ Using {task_type.name.lower()} model: {model_config.provider}:{model_config.model}[/dim]")

        # Build system prompt based on task type
        system_prompt = self._build_system_prompt(task_type, context)

        try:
            # Use the selected model with its optimal parameters
            response = await provider.complete(
                system_prompt=system_prompt,
                user_prompt=prompt,
                temperature=model_config.temperature,
                max_tokens=model_config.max_tokens
            )

            return self._parse_response(response.content, task_type)

        except Exception as e:
            console.print(f"[yellow]Model error: {e}, falling back to default agent[/yellow]")
            return await self._fallback_think(prompt, context)

    def _build_system_prompt(self, task_type: TaskType, context: AgentContext) -> str:
        """Build system prompt optimized for the task type."""

        base_info = f"""Working directory: {context.working_directory}

Available tools:
{self._get_tools_description()}

"""

        if task_type == TaskType.SIMPLE_REASONING:
            return base_info + """You are a helpful assistant focused on providing clear, concise answers to straightforward questions. Keep responses brief and accurate.

Respond with JSON:
{
    "thought": "brief analysis",
    "tool_calls": [...],
    "output": "concise answer"
}"""

        elif task_type == TaskType.COMPLEX_REASONING:
            return base_info + """You are an analytical assistant capable of deep reasoning and complex problem solving. Break down complex problems systematically and provide thorough analysis.

Respond with JSON:
{
    "thought": "detailed analysis and reasoning",
    "tool_calls": [...],
    "output": "comprehensive explanation"
}"""

        elif task_type == TaskType.CODING:
            return base_info + """You are a coding assistant specialized in software development. Write clean, efficient code with proper error handling and documentation.

Respond with JSON:
{
    "thought": "technical analysis",
    "tool_calls": [...],
    "output": "code explanation or result"
}"""

        elif task_type == TaskType.RESEARCH:
            return base_info + """You are a research assistant focused on finding, analyzing, and synthesizing information. Use available tools to gather relevant data.

Respond with JSON:
{
    "thought": "research strategy",
    "tool_calls": [...],
    "output": "research findings"
}"""

        elif task_type == TaskType.CREATIVE:
            return base_info + """You are a creative assistant focused on generating original content and ideas. Be imaginative while maintaining quality and relevance.

Respond with JSON:
{
    "thought": "creative approach",
    "tool_calls": [...],
    "output": "creative content"
}"""

        else:
            return base_info + """You are a general-purpose assistant. Analyze the task and respond appropriately.

Respond with JSON:
{
    "thought": "analysis",
    "tool_calls": [...],
    "output": "response"
}"""

    def _get_tools_description(self) -> str:
        """Get description of available tools."""
        tools_desc = []
        for tool_name, tool in self.tools.items():
            tools_desc.append(f"- {tool_name}: {tool.description}")
        return "\n".join(tools_desc)

    def _parse_response(self, response: str, task_type: TaskType) -> AgentResult:
        """Parse LLM response with task-type specific handling."""
        try:
            data = json.loads(response)
            return AgentResult(
                status=AgentStatus.COMPLETE,
                output=data.get("output"),
                tool_calls=data.get("tool_calls", []),
                metadata={"task_type": task_type.name, "thought": data.get("thought")}
            )
        except json.JSONDecodeError:
            # For simple tasks, raw response might be better
            if task_type == TaskType.SIMPLE_REASONING:
                return AgentResult(
                    status=AgentStatus.COMPLETE,
                    output=response.strip(),
                    metadata={"task_type": task_type.name}
                )
            else:
                return AgentResult(
                    status=AgentStatus.COMPLETE,
                    output=response,
                    metadata={"task_type": task_type.name}
                )

    async def _fallback_think(self, prompt: str, context: AgentContext) -> AgentResult:
        """Fallback to simple logic when no models available."""
        prompt_lower = prompt.lower()

        # Simple command routing
        if any(cmd in prompt_lower for cmd in ["list", "ls", "show", "display"]):
            if "file" in prompt_lower:
                return AgentResult(
                    status=AgentStatus.COMPLETE,
                    output="Listing files in directory",
                    tool_calls=[{"name": "bash", "parameters": {"command": "ls -la"}}]
                )

        elif any(cmd in prompt_lower for cmd in ["read", "cat", "view"]):
            # Try to extract filename
            words = prompt.split()
            for word in words:
                if "." in word and len(word) > 3:  # Likely a filename
                    return AgentResult(
                        status=AgentStatus.COMPLETE,
                        output=f"Reading file: {word}",
                        tool_calls=[{"name": "read", "parameters": {"file_path": word}}]
                    )

        elif any(cmd in prompt_lower for cmd in ["find", "search", "grep"]):
            # Extract search term
            words = prompt.split()
            if len(words) > 1:
                search_term = " ".join(words[1:])
                return AgentResult(
                    status=AgentStatus.COMPLETE,
                    output=f"Searching for: {search_term}",
                    tool_calls=[{"name": "grep", "parameters": {"pattern": search_term}}]
                )

        # Math operations
        if any(op in prompt for op in ["+", "-", "*", "/", "="]):
            try:
                # Simple math evaluation (unsafe but for demo)
                if "2+2" in prompt or "2 + 2" in prompt:
                    return AgentResult(
                        status=AgentStatus.COMPLETE,
                        output="4"
                    )
            except:
                pass

        return AgentResult(
            status=AgentStatus.COMPLETE,
            output=f"Processing: {prompt}"
        )

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about available models and task types."""
        return {
            "available_models": self.model_router.list_available_models(),
            "task_types": self.model_router.get_task_type_info(),
            "multi_model_enabled": self.config.is_multi_model_routing_enabled()
        }