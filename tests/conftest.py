"""Pytest configuration for Clay tests."""

import pytest
import os
import shutil
import inspect
import uuid
from pathlib import Path
from clay.trace import clear_trace, save_trace_file, get_trace_collector


@pytest.fixture(autouse=True)
def auto_cleanup(request):
    """Automatically clean up artifacts and prepare test environment."""
    # Clear any existing traces before test
    clear_trace()

    # Store original working directory
    original_cwd = os.getcwd()

    # Create clean test directory based on test name
    test_name = request.node.name
    project_root = Path(__file__).parent.parent
    test_dir = project_root / "_test" / test_name

    # Clear and create test directory
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True, exist_ok=True)

    # Change to test directory so all artifacts go there
    os.chdir(test_dir)

    yield

    # Save trace file if there are any trace events
    try:
        collector = get_trace_collector()
        events = collector.get_events()
        if events:
            # Save trace in the test directory before changing back
            trace_filepath = save_trace_file(test_name)
            print(f"Trace saved: {trace_filepath}")
    except Exception as e:
        # Don't fail the test if trace saving fails
        print(f"Warning: Failed to save trace: {e}")

    # Clear traces after saving
    clear_trace()

    # Safely restore working directory after test
    try:
        os.chdir(original_cwd)
    except (OSError, FileNotFoundError):
        # Directory was deleted, just go to the original directory
        os.chdir(original_cwd)
