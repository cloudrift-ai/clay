"""Configuration management for Clay."""

import os
import tomllib
from pathlib import Path
from typing import Dict, Any, Optional
import logging
import sys

logger = logging.getLogger(__name__)


class ClayConfig:
    """Configuration manager for Clay that supports multiple config sources."""

    def __init__(self):
        self.config = {}
        self._load_config()

    def _load_config(self):
        """Load configuration from multiple sources in priority order."""
        # 1. Default configuration
        self.config = {
            'providers': {},
            'defaults': {
                'provider': None,
                'model': None,
                'fast_mode': False,
                'verbose': False
            },
            'orchestrator': {
                'enabled': True,
                'max_retries': 3,
                'timeout_minutes': 30,
                'max_tokens': 100000
            },
            'models': {
                'multi_model_routing': False,
                'task_types': {
                    'simple_reasoning': {
                        'preferred_providers': ['cloudrift', 'openai', 'anthropic'],
                        'temperature': 0.3,
                        'max_tokens': 2048
                    },
                    'complex_reasoning': {
                        'preferred_providers': ['anthropic', 'openai', 'cloudrift'],
                        'temperature': 0.5,
                        'max_tokens': 8192
                    },
                    'coding': {
                        'preferred_providers': ['anthropic', 'cloudrift', 'openai'],
                        'temperature': 0.2,
                        'max_tokens': 8192
                    },
                    'creative': {
                        'preferred_providers': ['anthropic', 'openai', 'cloudrift'],
                        'temperature': 0.8,
                        'max_tokens': 4096
                    },
                    'research': {
                        'preferred_providers': ['anthropic', 'openai', 'cloudrift'],
                        'temperature': 0.4,
                        'max_tokens': 8192
                    }
                }
            }
        }

        # 2. Load from global config file (~/.clay/config.toml)
        global_config_path = Path.home() / '.clay' / 'config.toml'
        if global_config_path.exists():
            try:
                with open(global_config_path, 'rb') as f:
                    global_config = tomllib.load(f)
                self._merge_config(global_config)
                logger.debug(f"Loaded global config from {global_config_path}")
            except Exception as e:
                logger.warning(f"Failed to load global config: {e}")

        # 3. Load from project config file (.clay.toml)
        project_config_path = Path.cwd() / '.clay.toml'
        if project_config_path.exists():
            try:
                with open(project_config_path, 'rb') as f:
                    project_config = tomllib.load(f)
                self._merge_config(project_config)
                logger.debug(f"Loaded project config from {project_config_path}")
            except Exception as e:
                logger.warning(f"Failed to load project config: {e}")

        # 4. Load from environment variables (highest priority)
        self._load_from_environment()

    def _merge_config(self, new_config: Dict[str, Any]):
        """Merge new configuration into existing config."""
        for key, value in new_config.items():
            if key in self.config and isinstance(self.config[key], dict) and isinstance(value, dict):
                self.config[key].update(value)
            else:
                self.config[key] = value

    def _load_from_environment(self):
        """Load configuration from environment variables."""
        # API Keys
        env_providers = {}

        if os.getenv('CLOUDRIFT_API_KEY'):
            env_providers['cloudrift'] = {
                'api_key': os.getenv('CLOUDRIFT_API_KEY'),
                'model': os.getenv('CLOUDRIFT_MODEL')
            }

        if os.getenv('ANTHROPIC_API_KEY'):
            env_providers['anthropic'] = {
                'api_key': os.getenv('ANTHROPIC_API_KEY'),
                'model': os.getenv('ANTHROPIC_MODEL')
            }

        if os.getenv('OPENAI_API_KEY'):
            env_providers['openai'] = {
                'api_key': os.getenv('OPENAI_API_KEY'),
                'model': os.getenv('OPENAI_MODEL')
            }

        if env_providers:
            self.config['providers'].update(env_providers)

        # Other environment variables
        if os.getenv('CLAY_PROVIDER'):
            self.config['defaults']['provider'] = os.getenv('CLAY_PROVIDER')

        if os.getenv('CLAY_MODEL'):
            self.config['defaults']['model'] = os.getenv('CLAY_MODEL')

        if os.getenv('CLAY_VERBOSE') in ['1', 'true', 'True']:
            self.config['defaults']['verbose'] = True

    def get_provider_config(self, provider_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific provider."""
        return self.config.get('providers', {}).get(provider_name)

    def get_available_providers(self) -> Dict[str, Dict[str, Any]]:
        """Get all available providers with API keys."""
        return {
            name: config for name, config in self.config.get('providers', {}).items()
            if config.get('api_key')
        }

    def get_default_provider(self) -> Optional[str]:
        """Get the default provider name."""
        # Check explicit default
        default = self.config.get('defaults', {}).get('provider')
        if default:
            return default

        # Auto-detect first available provider
        available = self.get_available_providers()
        if available:
            # Prefer order: cloudrift, anthropic, openai
            for preferred in ['cloudrift', 'anthropic', 'openai']:
                if preferred in available:
                    return preferred
            # Return first available if none of the preferred ones
            return next(iter(available))

        return None

    def get_provider_credentials(self, provider_name: str) -> tuple[Optional[str], Optional[str]]:
        """Get API key and model for a provider."""
        provider_config = self.get_provider_config(provider_name)
        if provider_config:
            return provider_config.get('api_key'), provider_config.get('model')
        return None, None

    def get_default(self, key: str, fallback=None):
        """Get a default configuration value."""
        return self.config.get('defaults', {}).get(key, fallback)

    def get_orchestrator_config(self) -> Dict[str, Any]:
        """Get orchestrator configuration."""
        return self.config.get('orchestrator', {})

    def get_models_config(self) -> Dict[str, Any]:
        """Get models configuration."""
        return self.config.get('models', {})

    def is_multi_model_routing_enabled(self) -> bool:
        """Check if multi-model routing is enabled."""
        return False  # Simplified to always use single model

    def get_task_type_config(self, task_type: str) -> Dict[str, Any]:
        """Get configuration for a specific task type."""
        task_types = self.get_models_config().get('task_types', {})
        return task_types.get(task_type, {})

    def has_any_api_key(self) -> bool:
        """Check if any API key is configured."""
        providers = self.get_available_providers()
        return len(providers) > 0

    def prompt_for_api_key(self) -> Optional[tuple[str, str]]:
        """Prompt user for API key selection on first run."""
        from rich.console import Console
        from rich.panel import Panel
        from rich.prompt import Prompt, Confirm

        console = Console()

        # Check if running in non-interactive mode
        if not sys.stdin.isatty():
            return None

        console.print("\n[bold cyan]Welcome to Clay![/bold cyan]")
        console.print("It looks like this is your first time running Clay.\n")

        console.print(Panel(
            "Clay needs an API key to work with AI models.\n"
            "You can use one of the following providers:\n\n"
            "[bold]1. Cloudrift[/bold] (Recommended) - Fast, affordable Claude access\n"
            "   Get your key at: https://www.cloudrift.com\n\n"
            "[bold]2. Anthropic[/bold] - Direct Claude API access\n"
            "   Get your key at: https://console.anthropic.com\n\n"
            "[bold]3. OpenAI[/bold] - GPT models\n"
            "   Get your key at: https://platform.openai.com",
            title="[bold]API Key Setup[/bold]",
            border_style="cyan"
        ))

        # Ask which provider
        provider_choice = Prompt.ask(
            "\nWhich provider would you like to use?",
            choices=["1", "2", "3", "cloudrift", "anthropic", "openai"],
            default="1"
        )

        # Map choice to provider name
        provider_map = {
            "1": "cloudrift",
            "2": "anthropic",
            "3": "openai",
            "cloudrift": "cloudrift",
            "anthropic": "anthropic",
            "openai": "openai"
        }

        provider = provider_map.get(provider_choice, "cloudrift")

        # Prompt for API key
        api_key = Prompt.ask(f"\nEnter your {provider.upper()} API key", password=True)

        if not api_key:
            console.print("[yellow]No API key provided. You can set it later.[/yellow]")
            return None

        # Ask if they want to save to config
        save_to_config = Confirm.ask(
            "\nWould you like to save this API key to your config file?",
            default=True
        )

        if save_to_config:
            config_path = Path.home() / '.clay' / 'config.toml'
            self.save_api_key(provider, api_key, config_path)
            console.print(f"[green]✓ API key saved to {config_path}[/green]")

        return provider, api_key

    def save_api_key(self, provider: str, api_key: str, config_path: Path):
        """Save API key to configuration file."""
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing config or create new one
        config_data = {}
        if config_path.exists():
            try:
                with open(config_path, 'rb') as f:
                    config_data = tomllib.load(f)
            except Exception:
                pass

        # Update provider configuration
        if 'providers' not in config_data:
            config_data['providers'] = {}
        if provider not in config_data['providers']:
            config_data['providers'][provider] = {}

        config_data['providers'][provider]['api_key'] = api_key

        # Set default provider if not set
        if 'defaults' not in config_data:
            config_data['defaults'] = {}
        if 'provider' not in config_data['defaults']:
            config_data['defaults']['provider'] = provider

        # Write config file in TOML format
        self._write_toml_config(config_path, config_data)

        # Reload configuration
        self._load_config()

    def _write_toml_config(self, config_path: Path, config_data: dict):
        """Write configuration data to TOML file."""
        lines = []
        lines.append("# Clay Configuration File")
        lines.append("# Generated by Clay first-run setup\n")

        # Write defaults section
        if 'defaults' in config_data:
            lines.append("[defaults]")
            for key, value in config_data['defaults'].items():
                if isinstance(value, str):
                    lines.append(f'{key} = "{value}"')
                elif isinstance(value, bool):
                    lines.append(f'{key} = {"true" if value else "false"}')
                else:
                    lines.append(f'{key} = {value}')
            lines.append("")

        # Write providers section
        if 'providers' in config_data:
            for provider_name, provider_config in config_data['providers'].items():
                lines.append(f"[providers.{provider_name}]")
                for key, value in provider_config.items():
                    if isinstance(value, str):
                        lines.append(f'{key} = "{value}"')
                    else:
                        lines.append(f'{key} = {value}')
                lines.append("")

        # Write orchestrator section if exists
        if 'orchestrator' in config_data:
            lines.append("[orchestrator]")
            for key, value in config_data['orchestrator'].items():
                if isinstance(value, str):
                    lines.append(f'{key} = "{value}"')
                elif isinstance(value, bool):
                    lines.append(f'{key} = {"true" if value else "false"}')
                else:
                    lines.append(f'{key} = {value}')

        with open(config_path, 'w') as f:
            f.write('\n'.join(lines))

    def create_default_config(self, config_path: Path):
        """Create a default configuration file."""
        config_path.parent.mkdir(parents=True, exist_ok=True)

        default_config = '''# Clay Configuration File
# See https://docs.clay.ai/configuration for full documentation

[defaults]
# Default provider to use (optional - will auto-detect if not specified)
# provider = "cloudrift"

# Default model to use (optional)
# model = "claude-3-5-sonnet-20241022"

# Enable verbose output by default
verbose = false

# Enable fast mode by default
fast_mode = false

[providers.cloudrift]
# API key for Cloudrift (can also be set via CLOUDRIFT_API_KEY environment variable)
# api_key = "your-api-key-here"

# Default model for Cloudrift
# model = "claude-3-5-sonnet-20241022"

[providers.anthropic]
# API key for Anthropic (can also be set via ANTHROPIC_API_KEY environment variable)
# api_key = "your-api-key-here"

# Default model for Anthropic
# model = "claude-3-5-sonnet-20241022"

[providers.openai]
# API key for OpenAI (can also be set via OPENAI_API_KEY environment variable)
# api_key = "your-api-key-here"

# Default model for OpenAI
# model = "gpt-4"

[orchestrator]
# Enable orchestrator by default
enabled = true

# Maximum number of retries for failed operations
max_retries = 3

# Timeout for operations in minutes
timeout_minutes = 30

# Maximum tokens to use per task
max_tokens = 100000
'''

        with open(config_path, 'w') as f:
            f.write(default_config)


# Global config instance
_config = None

def get_config() -> ClayConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = ClayConfig()
    return _config

def reload_config():
    """Reload the configuration from files."""
    global _config
    _config = ClayConfig()