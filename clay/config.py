"""Configuration management for Clay."""

import os
import tomllib
from pathlib import Path
from typing import Dict, Any, Optional
import logging

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