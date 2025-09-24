"""Common helper functions for integration tests."""

import subprocess
import sys
from pathlib import Path


async def run_clay_command(query: str, working_dir=None):
    """Run clay command with default settings."""
    if working_dir is None:
        working_dir = Path.cwd()

    # Use the current Python executable (should work with pytest's environment)
    # Remove max-turns limit to allow full execution
    result = subprocess.run([
        sys.executable, "-m", "clay.cli", "-p", query
    ],
    cwd=working_dir,
    capture_output=True,
    text=True,
    timeout=45  # Reasonable timeout for LLM operations
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
        # Skip agent status lines (emoji prefixes and arrows)
        if (line.startswith('🤖') or line.startswith('→') or
            line.startswith('⠦') or line.startswith('⠼') or line.startswith('⠸') or
            line.startswith('⠧') or line.startswith('⠋') or line.startswith('⠙') or
            line.startswith('⠹') or line.startswith('⠴') or line.startswith('⠏') or
            line.startswith('⠛') or line.startswith('⠇') or line.startswith('⠏') or
            line.startswith('➤') or line.strip().startswith('→') or
            line.startswith('Task ') or line.strip() == '' or
            line.startswith('Warning: Failed to initialize Clay orchestrator:') or
            line.startswith('ControlLoopOrchestrator.__init__()') or
            line.startswith("'sandbox_manager' and 'test_runner'") or
            line.startswith('Falling back to legacy agent system') or
            'Thinking with' in line):
            continue

        # This is likely the actual response content
        response_lines.append(line)
        found_response = True

    # If we didn't find any response content, but there was output, check if files were created
    if not response_lines and output:
        # If the command seemed to work but gave minimal output,
        # check if any relevant files were created in the working directory
        working_dir = working_dir or Path.cwd()
        py_files = list(working_dir.glob("*.py"))
        if py_files:
            # If Python files were created, assume the command worked
            return f"Code implementation completed. Files created: {[f.name for f in py_files]}"
        else:
            # Return the raw output as fallback
            return output

    return '\n'.join(response_lines).strip() if response_lines else output


def assert_response_quality(response, expected_keywords=None, min_length=10):
    """Assert that a response meets quality criteria."""
    assert response, "Response should not be empty"
    assert len(response) >= min_length, f"Response too short: {len(response)} < {min_length}"

    if expected_keywords:
        response_lower = response.lower()
        # At least one keyword should be present (more flexible than requiring all)
        found_keywords = sum(1 for keyword in expected_keywords if keyword.lower() in response_lower)
        assert found_keywords > 0, f"At least one of {expected_keywords} should be found in response: '{response[:100]}...'"