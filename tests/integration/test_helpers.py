"""Common helper functions for integration tests."""

import subprocess
import sys
from pathlib import Path


async def run_clay_command(query: str, working_dir=None):
    """Run clay command with default settings."""
    if working_dir is None:
        working_dir = Path.cwd()

    # Use the current Python executable (should work with pytest's environment)
    result = subprocess.run([
        sys.executable, "-m", "clay.cli", "-p", query
    ],
    cwd=working_dir,
    capture_output=True,
    text=True,
    timeout=30
    )

    if result.returncode != 0:
        raise Exception(f"Clay command failed: {result.stderr}")

    # Extract just the response (skip the agent output lines)
    output = result.stdout.strip()
    lines = output.split('\n')

    # Find the actual response after agent processing
    response_lines = []
    found_response = False
    for line in lines:
        if found_response:
            response_lines.append(line)
        elif not line.startswith('🤖') and not line.startswith('→') and not line.startswith('⠦') and not line.startswith('⠼') and not line.startswith('⠸'):
            # This is likely the actual response
            response_lines.append(line)
            found_response = True

    return '\n'.join(response_lines).strip()


def assert_response_quality(response, expected_keywords=None, min_length=10):
    """Assert that a response meets quality criteria."""
    assert response, "Response should not be empty"
    assert len(response) >= min_length, f"Response too short: {len(response)} < {min_length}"

    if expected_keywords:
        response_lower = response.lower()
        for keyword in expected_keywords:
            assert keyword.lower() in response_lower, f"Expected keyword '{keyword}' not found in response"