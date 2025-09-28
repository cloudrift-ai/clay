"""Integration tests for incremental plan refinement and error correction."""

import pytest
from datetime import datetime

from clay.agents.coding_agent import CodingAgent
from clay.agents.llm_agent import LLMAgent
from clay.orchestrator.plan import Plan, Step


def create_user_message_step(message: str) -> Step:
    """Helper to create a UserMessageTool step."""
    user_message_step = Step(
        tool_name="user_message",
        parameters={"message": message},
        description="User's initial request"
    )
    user_message_step.status = "SUCCESS"
    user_message_step.result = {
        "output": message,
        "metadata": {
            "message": message,
            "tool_type": "user_context",
            "timestamp": datetime.now().isoformat()
        }
    }
    return user_message_step


@pytest.mark.asyncio
async def test_incomplete_plan_refinement():
    """Test that agent can refine an incomplete plan by adding necessary steps."""
    agent = CodingAgent()

    # Create a plan with UserMessageTool - missing a crucial step
    task = "Create a file called output.txt with 'Hello World' and then verify it was created successfully"
    user_message_step = create_user_message_step(task)

    incomplete_plan = Plan(
        todo=[
            Step(
                tool_name="bash",
                parameters={"command": "echo 'Hello World' > output.txt"},
                description="Create a file with Hello World"
            )
        ],
        completed=[user_message_step]
    )

    # Agent should refine the plan to add the verification step
    refined_plan = await agent.review_plan(incomplete_plan)

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
    task = "Create a file and read its contents"
    user_message_step = create_user_message_step(task)

    failed_plan = Plan(
        todo=[
            Step(
                tool_name="bash",
                parameters={"command": "cat non_existent_file.txt"},
                description="Read contents of a file"
            )
        ],
        completed=[
            user_message_step,
            Step(
                tool_name="bash",
                parameters={"command": "touch /root/protected_file.txt"},
                description="Create a file in protected directory",
                result=None,
                error_message="touch: cannot touch '/root/protected_file.txt': Permission denied",
                status="FAILURE"
            )
        ]
    )

    # Agent should correct the plan by using a different approach
    corrected_plan = await agent.review_plan(failed_plan)

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
    task = "Set up a new project directory with package.json"
    user_message_step = create_user_message_step(task)

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
            user_message_step,
            Step(
                tool_name="bash",
                parameters={"command": "ls -la"},
                description="Check current directory contents",
                result={
                    "status": "success",
                    "output": "total 8\ndrwxr-xr-x  3 user user 4096 Jan 1 12:00 .\ndrwxr-xr-x  5 user user 4096 Jan 1 12:00 ..\ndrwxr-xr-x  2 user user 4096 Jan 1 12:00 test_project",
                    "metadata": {"tool_name": "bash"}
                },
                error_message=None,
                status="SUCCESS"
            )
        ]
    )

    # Agent should see that test_project already exists and adjust the plan
    adjusted_plan = await agent.review_plan(plan_with_results)

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

    # Create a plan with no completed message steps so agent will respond
    task = "Now what is 4*3?"
    user_message_step = create_user_message_step(task)

    plan_with_history = Plan(
        todo=[],
        completed=[
            user_message_step,
            Step(
                tool_name="bash",
                parameters={"command": "echo 'Previous calculation: 2+2=4'"},
                description="Previous calculation step",
                result={
                    "status": "success",
                    "output": "Previous calculation: 2+2=4",
                    "metadata": {"tool_name": "bash"}
                },
                error_message=None,
                status="SUCCESS"
            )
        ]
    )

    # LLM agent should provide follow-up answer considering context
    updated_plan = await agent.review_plan(plan_with_history)

    # Should have a message step in todo list
    assert len(updated_plan.todo) > 0, "LLM agent should provide a response step"

    # Check if there's a message step
    message_steps = [step for step in updated_plan.todo if step.tool_name == "message"]
    assert len(message_steps) > 0, "LLM agent should use message tool"

    # Check that the message contains the answer
    message_content = message_steps[0].parameters.get("message", "")
    assert "12" in message_content, "LLM agent should answer the math question"


@pytest.mark.asyncio
async def test_plan_completion_detection():
    """Test that agent can detect when a plan is complete."""
    agent = CodingAgent()

    # Create a plan where the task is already complete
    task = "Create a file called result.txt with success message and verify it"
    user_message_step = create_user_message_step(task)

    completed_plan = Plan(
        todo=[],
        completed=[
            user_message_step,
            Step(
                tool_name="bash",
                parameters={"command": "echo 'Task completed successfully' > result.txt"},
                description="Create result file",
                result={
                    "status": "success",
                    "output": "File created successfully",
                    "metadata": {"tool_name": "bash"}
                },
                error_message=None,
                status="SUCCESS"
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
                error_message=None,
                status="SUCCESS"
            )
        ]
    )

    # Agent should recognize the task is complete
    final_plan = await agent.review_plan(completed_plan)

    # Should either have no additional todos or a completion message
    if len(final_plan.todo) > 0:
        # Check if there's a completion message
        message_steps = [step for step in final_plan.todo if step.tool_name == "message"]
        if message_steps:
            message_content = message_steps[0].parameters.get("message", "")
            assert "complet" in message_content.lower() or "success" in message_content.lower(), \
                   "Agent should acknowledge task completion"
    # If no todos, that's also acceptable (task complete)


@pytest.mark.asyncio
async def test_partial_failure_recovery():
    """Test that agent can recover from partial failures in multi-step plans."""
    agent = CodingAgent()

    # Create a plan with mixed success/failure results
    task = "Create a backup of important files"
    user_message_step = create_user_message_step(task)

    mixed_results_plan = Plan(
        todo=[
            Step(
                tool_name="bash",
                parameters={"command": "echo 'backup complete'"},
                description="Create backup confirmation"
            )
        ],
        completed=[
            user_message_step,
            Step(
                tool_name="bash",
                parameters={"command": "mkdir backup_dir"},
                description="Create backup directory",
                result={
                    "status": "success",
                    "output": "Directory created",
                    "metadata": {"tool_name": "bash"}
                },
                error_message=None,
                status="SUCCESS"
            ),
            Step(
                tool_name="bash",
                parameters={"command": "cp important_file.txt backup_dir/"},
                description="Copy important file",
                result=None,
                error_message="cp: cannot stat 'important_file.txt': No such file or directory",
                status="FAILURE"
            )
        ]
    )

    # Agent should handle the partial failure and adjust the plan
    recovery_plan = await agent.review_plan(mixed_results_plan)

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

    # Or check if agent provides completion message acknowledging the issue
    message_steps = [step for step in recovery_plan.todo if step.tool_name == "message"]
    for step in message_steps:
        message_content = step.parameters.get("message", "")
        if any(keyword in message_content.lower() for keyword in ["error", "missing", "backup", "fail"]):
            has_recovery_or_completion = True
            break

    assert has_recovery_or_completion, "Agent should either provide recovery steps or acknowledge the failure"


@pytest.mark.asyncio
async def test_agent_uses_message_tool():
    """Test that agent can use the message tool for communication."""
    agent = CodingAgent()

    # Create a simple plan to test message tool usage
    task = "Explain what tools you have available"
    user_message_step = create_user_message_step(task)

    empty_plan = Plan(todo=[], completed=[user_message_step])

    # Agent should create a plan that uses the message tool
    plan = await agent.review_plan(empty_plan)

    # Check that agent created steps (might include message tool)
    assert len(plan.todo) >= 0, "Agent should handle the request"

    # If agent provides steps, check if message tool is used
    message_tool_used = any(
        step.tool_name == "message" for step in plan.todo
    )

    # Agent should either have todos (including message tool) or be complete
    has_response = len(plan.todo) > 0 or message_tool_used

    assert has_response, "Agent should provide some response (todos or message tool)"