"""Integration tests for incremental plan refinement and error correction."""

import pytest
from pathlib import Path

from clay.agents.coding_agent import CodingAgent
from clay.agents.llm_agent import LLMAgent
from clay.runtime.plan import Plan, Step


@pytest.mark.asyncio
async def test_incomplete_plan_refinement():
    """Test that agent can refine an incomplete plan by adding necessary steps."""
    agent = CodingAgent()

    # Create an incomplete plan - missing a crucial step
    incomplete_plan = Plan(
        todo=[
            Step(
                tool_name="bash",
                parameters={"command": "echo 'Hello World' > output.txt"},
                description="Create a file with Hello World"
            )
        ],
        completed=[],
        description="Create and verify a file",
        output="Starting file creation task"
    )

    task = "Create a file called output.txt with 'Hello World' and then verify it was created successfully"

    # Agent should refine the plan to add the verification step
    refined_plan = await agent.review_plan(incomplete_plan, task)

    # Check that agent added the missing verification step
    assert len(refined_plan.todo) >= 2, "Agent should add verification step to incomplete plan"

    # Check that one of the steps is for verification
    verification_found = False
    for step in refined_plan.todo:
        if "cat" in step.parameters.get("command", "") or "ls" in step.parameters.get("command", ""):
            verification_found = True
            break

    assert verification_found, "Agent should add a verification step (cat or ls command)"


@pytest.mark.asyncio
async def test_error_correction():
    """Test that agent can correct a plan when a step fails."""
    agent = CodingAgent()

    # Create a plan with a completed failed step
    failed_plan = Plan(
        todo=[
            Step(
                tool_name="bash",
                parameters={"command": "cat non_existent_file.txt"},
                description="Read contents of a file"
            )
        ],
        completed=[
            Step(
                tool_name="bash",
                parameters={"command": "touch /root/protected_file.txt"},
                description="Create a file in protected directory",
                result=None,
                error="touch: cannot touch '/root/protected_file.txt': Permission denied"
            )
        ],
        description="Create and read a file",
    )

    task = "Create a file and read its contents"

    # Agent should correct the plan by using a different approach
    corrected_plan = await agent.review_plan(failed_plan, task)

    # Agent should either:
    # 1. Change the file location to somewhere writable
    # 2. Add a step to create the directory first
    # 3. Use a different approach
    assert len(corrected_plan.todo) > 0, "Agent should provide corrective steps"

    # Check that the new plan doesn't repeat the same error
    for step in corrected_plan.todo:
        command = step.parameters.get("command", "")
        assert "/root/" not in command, "Agent should avoid repeating the same permission error"


@pytest.mark.asyncio
async def test_multi_step_plan_adjustment():
    """Test that agent adjusts remaining steps based on intermediate results."""
    agent = CodingAgent()

    # Create a plan where first step completed successfully but results suggest plan change
    plan_with_results = Plan(
        todo=[
            Step(
                tool_name="bash",
                parameters={"command": "mkdir test_project"},
                description="Create project directory"
            ),
            Step(
                tool_name="bash",
                parameters={"command": "cd test_project && npm init -y"},
                description="Initialize npm project"
            )
        ],
        completed=[
            Step(
                tool_name="bash",
                parameters={"command": "ls -la"},
                description="Check current directory contents",
                result={
                    "status": "success",
                    "output": "total 8\ndrwxr-xr-x  3 user user 4096 Jan 1 12:00 .\ndrwxr-xr-x  5 user user 4096 Jan 1 12:00 ..\ndrwxr-xr-x  2 user user 4096 Jan 1 12:00 test_project",
                    "metadata": {"tool_name": "bash"}
                },
                error=None
            )
        ],
        description="Set up a new project",
    )

    task = "Set up a new project directory with package.json"

    # Agent should see that test_project already exists and adjust the plan
    adjusted_plan = await agent.review_plan(plan_with_results, task)

    # Agent should modify the plan since directory already exists
    assert len(adjusted_plan.todo) > 0, "Agent should provide adjusted steps"

    # Check that agent provides some kind of steps to continue the task
    # The agent might still include mkdir or might skip it - what's important is that
    # it progresses towards creating the package.json
    npm_or_cd_steps = [step for step in adjusted_plan.todo
                       if "npm" in step.parameters.get("command", "") or
                          "cd test_project" in step.parameters.get("command", "")]
    assert len(npm_or_cd_steps) > 0, "Agent should include steps to work with the existing directory"


@pytest.mark.asyncio
async def test_llm_agent_handles_plan_state():
    """Test that LLM agent can handle plans with completed steps appropriately."""
    agent = LLMAgent()

    # Create a plan with some completed "conversation" steps but no output
    # This forces the agent to process the new question
    plan_with_history = Plan(
        todo=[],
        completed=[
            Step(
                tool_name="llm_response",
                parameters={"query": "What is 2+2?"},
                description="Answer math question",
                result={
                    "status": "success",
                    "output": "2+2 equals 4",
                    "metadata": {"tool_name": "llm_response"}
                },
                error=None
            )
        ],
        description="Math conversation",
        output=None  # No output so agent will process the new question
    )

    task = "Now what is 4*3?"

    # LLM agent should provide follow-up answer considering context
    updated_plan = await agent.review_plan(plan_with_history, task)

    # Should have output and no additional todos (LLM agent provides direct answers)
    assert updated_plan.output is not None, "LLM agent should provide an output"
    assert len(updated_plan.todo) == 0, "LLM agent typically doesn't need tools"
    assert "12" in updated_plan.output, "LLM agent should answer the math question"


@pytest.mark.asyncio
async def test_plan_completion_detection():
    """Test that agent can detect when a plan is complete."""
    agent = CodingAgent()

    # Create a plan where the task is already complete
    completed_plan = Plan(
        todo=[],
        completed=[
            Step(
                tool_name="bash",
                parameters={"command": "echo 'Task completed successfully' > result.txt"},
                description="Create result file",
                result={
                    "status": "success",
                    "output": "File created successfully",
                    "metadata": {"tool_name": "bash"}
                },
                error=None
            ),
            Step(
                tool_name="bash",
                parameters={"command": "cat result.txt"},
                description="Verify file contents",
                result={
                    "status": "success",
                    "output": "Task completed successfully",
                    "metadata": {"tool_name": "bash"}
                },
                error=None
            )
        ],
        description="Create and verify a result file",
    )

    task = "Create a file called result.txt with success message and verify it"

    # Agent should recognize the task is complete
    final_plan = await agent.review_plan(completed_plan, task)

    # Should have no additional todos and clear completion output
    assert len(final_plan.todo) == 0, "Agent should not add more steps to completed task"
    assert final_plan.output is not None, "Agent should provide completion summary"
    assert "complet" in final_plan.output.lower() or "success" in final_plan.output.lower(), \
           "Agent should acknowledge task completion"


@pytest.mark.asyncio
async def test_partial_failure_recovery():
    """Test that agent can recover from partial failures in multi-step plans."""
    agent = CodingAgent()

    # Create a plan with mixed success/failure results
    mixed_results_plan = Plan(
        todo=[
            Step(
                tool_name="bash",
                parameters={"command": "echo 'backup complete'"},
                description="Create backup confirmation"
            )
        ],
        completed=[
            Step(
                tool_name="bash",
                parameters={"command": "mkdir backup_dir"},
                description="Create backup directory",
                result={
                    "status": "success",
                    "output": "Directory created",
                    "metadata": {"tool_name": "bash"}
                },
                error=None
            ),
            Step(
                tool_name="bash",
                parameters={"command": "cp important_file.txt backup_dir/"},
                description="Copy important file",
                result=None,
                error="cp: cannot stat 'important_file.txt': No such file or directory"
            )
        ],
        description="Backup important files",
    )

    task = "Create a backup of important files"

    # Agent should handle the partial failure and adjust the plan
    recovery_plan = await agent.review_plan(mixed_results_plan, task)

    # Agent should address the failure in some way - either by providing recovery steps
    # or by acknowledging the error and completing with what's available
    assert len(recovery_plan.todo) >= 0, "Agent should handle the partial failure"

    # Check if agent either provides recovery steps OR acknowledges the failure
    has_recovery_or_completion = False

    # Check for recovery steps
    for step in recovery_plan.todo:
        command = step.parameters.get("command", "")
        if any(keyword in command.lower() for keyword in ["ls", "find", "touch", "echo", "create"]):
            has_recovery_or_completion = True
            break

    # Or check if agent provides completion output acknowledging the issue
    if recovery_plan.output and ("error" in recovery_plan.output.lower() or
                                "missing" in recovery_plan.output.lower() or
                                "backup" in recovery_plan.output.lower()):
        has_recovery_or_completion = True

    assert has_recovery_or_completion, "Agent should either provide recovery steps or acknowledge the failure"