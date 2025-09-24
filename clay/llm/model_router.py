"""Multi-model routing system for different task types."""

from enum import Enum, auto
from typing import Dict, Optional, List, Any, Tuple
from dataclasses import dataclass
import re

from .base import LLMProvider
from .factory import create_llm_provider


class TaskType(Enum):
    """Different types of tasks that require different model capabilities."""
    SIMPLE_REASONING = auto()    # Basic Q&A, simple math, quick facts
    COMPLEX_REASONING = auto()   # Analysis, research, complex problem solving
    CODING = auto()             # Code generation, debugging, refactoring
    CREATIVE = auto()           # Writing, content generation
    RESEARCH = auto()           # Information gathering, web search analysis


@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    provider: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    description: str = ""


class ModelRouter:
    """Routes tasks to appropriate models based on task type and complexity."""

    def __init__(self, api_keys: Dict[str, str]):
        """Initialize with available API keys."""
        self.api_keys = api_keys
        self.providers_cache: Dict[str, LLMProvider] = {}

        # Define default model configurations for each task type
        self.model_configs = {
            TaskType.SIMPLE_REASONING: [
                ModelConfig("cloudrift", "deepseek-ai/DeepSeek-V3", 0.3, 2048, "Fast, efficient for simple tasks"),
                ModelConfig("openai", "gpt-3.5-turbo", 0.3, 2048, "Quick responses for basic queries"),
                ModelConfig("anthropic", "claude-3-haiku-20240307", 0.3, 2048, "Fast Claude model"),
            ],
            TaskType.COMPLEX_REASONING: [
                ModelConfig("anthropic", "claude-3-5-sonnet-20241022", 0.5, 8192, "Excellent reasoning capabilities"),
                ModelConfig("openai", "gpt-4", 0.5, 8192, "Strong analytical thinking"),
                ModelConfig("cloudrift", "deepseek-ai/DeepSeek-V3", 0.5, 8192, "DeepSeek reasoning via Cloudrift"),
            ],
            TaskType.CODING: [
                ModelConfig("anthropic", "claude-3-5-sonnet-20241022", 0.2, 8192, "Best for coding tasks"),
                ModelConfig("cloudrift", "deepseek-ai/DeepSeek-V3", 0.2, 8192, "DeepSeek coding via Cloudrift"),
                ModelConfig("openai", "gpt-4", 0.2, 8192, "Strong coding capabilities"),
            ],
            TaskType.CREATIVE: [
                ModelConfig("anthropic", "claude-3-5-sonnet-20241022", 0.8, 4096, "Creative writing"),
                ModelConfig("openai", "gpt-4", 0.8, 4096, "Creative content generation"),
                ModelConfig("cloudrift", "deepseek-ai/DeepSeek-V3", 0.8, 4096, "Creative DeepSeek"),
            ],
            TaskType.RESEARCH: [
                ModelConfig("anthropic", "claude-3-5-sonnet-20241022", 0.4, 8192, "Research and analysis"),
                ModelConfig("openai", "gpt-4", 0.4, 8192, "Information synthesis"),
                ModelConfig("cloudrift", "deepseek-ai/DeepSeek-V3", 0.4, 8192, "Research via Cloudrift"),
            ]
        }

    def classify_task(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> TaskType:
        """Classify a task based on the prompt and context."""
        prompt_lower = prompt.lower()

        # Simple reasoning patterns
        simple_patterns = [
            r'\b(what is|what are)\b.*\?',
            r'\b\d+\s*[\+\-\*\/]\s*\d+',  # Math operations
            r'\b(hello|hi|hey)\b',
            r'\b(yes|no)\b\s+questions?',
            r'\b(define|meaning of)\b',
            r'\b(true or false|t/f)\b',
        ]

        # Creative patterns (check first for specificity)
        creative_patterns = [
            r'\b(story|poem|article|fiction|narrative|tale)\b',
            r'\bcreative\b.*\b(story|writing|content|ideas)\b',
            r'\b(write|compose).*\b(story|poem|article|creative)\b',
            r'\b(imaginative|original|innovative|artistic)\b',
            r'\b(brainstorm|inspiration|ideas|concepts)\b',
        ]

        # Research patterns (specific research activities)
        research_patterns = [
            r'\b(research|investigate|find information|search for|lookup)\b',
            r'\b(summarize|synthesis|compile|gather).*\binformation\b',
            r'\b(latest|recent|current|trends|news)\b',
            r'\b(documentation|docs|reference|manual)\b',
        ]

        # Coding patterns (more specific to avoid false positives)
        coding_patterns = [
            r'\b(implement|code|program|function|class|method)\b',
            r'\bcreate.*\b(function|class|method|program|script|code)\b',
            r'\bwrite.*\b(function|class|method|program|script|code)\b',
            r'\bbuild.*\b(function|class|method|program|script|application)\b',
            r'\b(debug|fix|error|bug|refactor|optimize)\b',
            r'\b(python|javascript|java|c\+\+|rust|go|sql)\b',
            r'\b(algorithm|data structure|api|library|framework)\b',
            r'\.py\b|\.js\b|\.java\b|\.cpp\b|\.rs\b|\.go\b',
        ]

        # Complex reasoning patterns
        complex_patterns = [
            r'\b(analyze|compare|evaluate|assess|explain why|reasoning)\b',
            r'\b(strategy|approach|methodology|framework|architecture)\b',
            r'\b(pros and cons|advantages|disadvantages|tradeoffs)\b',
            r'\b(solution|problem solving|complex|difficult)\b',
        ]

        # Check patterns in order of specificity (most specific first)
        if any(re.search(pattern, prompt_lower) for pattern in creative_patterns):
            return TaskType.CREATIVE

        if any(re.search(pattern, prompt_lower) for pattern in research_patterns):
            return TaskType.RESEARCH

        if any(re.search(pattern, prompt_lower) for pattern in coding_patterns):
            return TaskType.CODING

        if any(re.search(pattern, prompt_lower) for pattern in complex_patterns):
            return TaskType.COMPLEX_REASONING

        if any(re.search(pattern, prompt_lower) for pattern in simple_patterns):
            return TaskType.SIMPLE_REASONING

        # Context-based classification
        if context:
            if context.get('working_directory') and any(
                file_ext in prompt_lower
                for file_ext in ['.py', '.js', '.java', '.cpp', '.rs', '.go']
            ):
                return TaskType.CODING

        # Default based on length and complexity
        if len(prompt.split()) < 10:
            return TaskType.SIMPLE_REASONING
        else:
            return TaskType.COMPLEX_REASONING

    def get_best_model(self, task_type: TaskType) -> Tuple[Optional[LLMProvider], Optional[ModelConfig]]:
        """Get the best available model for a given task type."""
        configs = self.model_configs.get(task_type, [])

        for config in configs:
            if config.provider in self.api_keys:
                provider_key = f"{config.provider}:{config.model}"

                if provider_key not in self.providers_cache:
                    try:
                        provider = create_llm_provider(
                            config.provider,
                            self.api_keys[config.provider],
                            config.model
                        )
                        self.providers_cache[provider_key] = provider
                    except Exception:
                        continue

                return self.providers_cache[provider_key], config

        return None, None

    def get_model_for_task(self, prompt: str, context: Optional[Dict[str, Any]] = None) -> Tuple[Optional[LLMProvider], TaskType, Optional[ModelConfig]]:
        """Get the appropriate model for a specific task."""
        task_type = self.classify_task(prompt, context)
        provider, config = self.get_best_model(task_type)
        return provider, task_type, config

    def list_available_models(self) -> Dict[TaskType, List[str]]:
        """List all available models by task type."""
        result = {}
        for task_type, configs in self.model_configs.items():
            available = []
            for config in configs:
                if config.provider in self.api_keys:
                    available.append(f"{config.provider}:{config.model} ({config.description})")
            result[task_type] = available
        return result

    def update_model_config(self, task_type: TaskType, provider: str, model: str, **kwargs):
        """Update or add a model configuration for a task type."""
        config = ModelConfig(provider, model, **kwargs)

        if task_type not in self.model_configs:
            self.model_configs[task_type] = []

        # Remove existing config for same provider/model combo
        self.model_configs[task_type] = [
            c for c in self.model_configs[task_type]
            if not (c.provider == provider and c.model == model)
        ]

        # Add new config at the beginning (highest priority)
        self.model_configs[task_type].insert(0, config)

    def get_task_type_info(self) -> Dict[str, str]:
        """Get information about different task types."""
        return {
            "SIMPLE_REASONING": "Basic Q&A, simple math, quick facts, yes/no questions",
            "COMPLEX_REASONING": "Analysis, research, complex problem solving, strategic thinking",
            "CODING": "Code generation, debugging, refactoring, algorithm implementation",
            "CREATIVE": "Writing, content generation, brainstorming, creative tasks",
            "RESEARCH": "Information gathering, web search analysis, documentation lookup"
        }