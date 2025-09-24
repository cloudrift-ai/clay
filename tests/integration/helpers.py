"""Helper utilities for integration tests."""

import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, List
import pytest

from clay.cli import ClaySession
from clay.config import get_config


class IntegrationTestHelper:
    """Helper class for integration tests."""

    def __init__(self):
        self.temp_dirs = []
        self.config = get_config()

    def create_temp_project(self, name: str = "test_project") -> Path:
        """Create a temporary project directory."""
        temp_dir = Path(tempfile.mkdtemp(prefix=f"clay_test_{name}_"))
        self.temp_dirs.append(temp_dir)
        return temp_dir

    def cleanup(self):
        """Clean up temporary directories."""
        for temp_dir in self.temp_dirs:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
        self.temp_dirs.clear()

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

    def assert_response_quality(self, response: str, expected_keywords: List[str] = None, min_length: int = 10):
        """Assert that a response meets quality criteria."""
        assert response, "Response should not be empty"
        assert len(response) >= min_length, f"Response too short: {len(response)} < {min_length}"

        if expected_keywords:
            response_lower = response.lower()
            for keyword in expected_keywords:
                assert keyword.lower() in response_lower, f"Expected keyword '{keyword}' not found in response"

    def assert_files_created(self, directory: Path, expected_files: List[str]):
        """Assert that expected files were created."""
        for file_path in expected_files:
            full_path = directory / file_path
            assert full_path.exists(), f"Expected file {file_path} was not created"
            assert full_path.stat().st_size > 0, f"File {file_path} is empty"