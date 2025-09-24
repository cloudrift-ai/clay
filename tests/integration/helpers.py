"""Helper utilities for integration tests."""

import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List
import pytest
import time

from clay.cli import ClaySession
from clay.config import get_config


class IntegrationTestHelper:
    """Helper class for integration tests."""

    def __init__(self):
        self.temp_dirs = []
        self.config = get_config()
        self.project_root = Path(__file__).parent.parent.parent  # Navigate to project root
        self.test_dir_root = self.project_root / "_test"

        # Clean up any existing test directories at the beginning
        if self.test_dir_root.exists():
            shutil.rmtree(self.test_dir_root)
        self.test_dir_root.mkdir(exist_ok=True)

    def create_temp_project(self, name: str = "test_project") -> Path:
        """Create a temporary project directory in _test folder."""
        # Create unique directory name with timestamp
        timestamp = str(int(time.time() * 1000))  # milliseconds for uniqueness
        dir_name = f"{name}_{timestamp}"
        temp_dir = self.test_dir_root / dir_name
        temp_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dirs.append(temp_dir)
        return temp_dir

    def cleanup(self):
        """No-op cleanup for easier inspection - directories are cleaned at initialization."""
        # Keep directories for inspection, they'll be cleaned up at the start of next test run
        pass

    async def create_session(self, working_dir: Path = None) -> ClaySession:
        """Create a Clay session for testing."""
        if working_dir is None:
            working_dir = self.create_temp_project()

        # Get API keys for testing
        api_keys = {}
        for provider in ['cloudrift', 'anthropic', 'openai']:
            key, _ = self.config.get_provider_credentials(provider)
            if key:
                api_keys[provider] = key

        if not api_keys:
            pytest.skip("No API keys available for integration testing")

        session = ClaySession(
            llm_provider=None,
            working_dir=str(working_dir),
            fast_mode=False,
            use_orchestrator=True
        )

        return session

    def assert_response_quality(self, response, expected_keywords: List[str] = None, min_length: int = 10):
        """Assert that a response meets quality criteria."""
        assert response, "Response should not be empty"

        # Handle both string and dictionary responses
        if isinstance(response, dict):
            # Convert dictionary to string for analysis
            import json
            response_str = json.dumps(response, indent=2)
        else:
            response_str = str(response)

        assert len(response_str) >= min_length, f"Response too short: {len(response_str)} < {min_length}"

        if expected_keywords:
            response_lower = response_str.lower()
            for keyword in expected_keywords:
                assert keyword.lower() in response_lower, f"Expected keyword '{keyword}' not found in response"

    def assert_files_created(self, directory: Path, expected_files: List[str]):
        """Assert that expected files were created."""
        for file_path in expected_files:
            full_path = directory / file_path
            assert full_path.exists(), f"Expected file {file_path} was not created"
            assert full_path.stat().st_size > 0, f"File {file_path} is empty"