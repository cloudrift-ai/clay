"""Tests for plan serialization and KV-cache optimization."""

import json
from pathlib import Path
from clay.orchestrator.plan import Plan, Step
from clay.orchestrator.orchestrator import ClayOrchestrator


class TestPlanSerialization:
    """Test plan serialization for KV-cache optimization."""

    def test_plan_structure_order(self):
        """Test that plans have completed items before todo items."""
        # Create a plan with some steps
        step1 = Step("write", {"file_path": "test.py", "content": "print('hello')"}, "Create test file")
        step2 = Step("bash", {"command": "python test.py"}, "Run test file")
        step3 = Step("write", {"file_path": "test2.py", "content": "print('world')"}, "Create second file")

        plan = Plan(todo=[step1, step2, step3])

        # Convert to dict and check structure
        plan_dict = plan.to_dict()

        # Verify that completed comes before todo in the structure
        keys = list(plan_dict.keys())
        assert keys.index("completed") < keys.index("todo"), "completed should come before todo"

        # Initially, all items should be in todo
        assert len(plan_dict["completed"]) == 0
        assert len(plan_dict["todo"]) == 3

    def test_plan_progression_maintains_prefix(self):
        """Test that as plans progress, they maintain stable prefixes for KV-cache optimization."""
        goal = "create test files"

        # Create initial plan
        step1 = Step("write", {"file_path": "test1.py", "content": "print('hello')"}, "Create first file")
        step2 = Step("write", {"file_path": "test2.py", "content": "print('world')"}, "Create second file")
        step3 = Step("bash", {"command": "python test1.py"}, "Run first file")

        plan = Plan(todo=[step1, step2, step3])

        # Simulate orchestrator plan structure
        def create_plan_data(plan, goal):
            return {
                "goal": goal,
                "plan": plan.to_dict()
            }

        # Serialize initial state (iteration 0)
        plan_data_0 = create_plan_data(plan, goal)
        json_0 = json.dumps(plan_data_0, indent=2)

        # Complete first step
        plan.complete_next_step({"output": "File created successfully"})
        plan_data_1 = create_plan_data(plan, goal)
        json_1 = json.dumps(plan_data_1, indent=2)

        # Complete second step
        plan.complete_next_step({"output": "Second file created"})
        plan_data_2 = create_plan_data(plan, goal)
        json_2 = json.dumps(plan_data_2, indent=2)

        # Complete third step
        plan.complete_next_step({"output": "hello\n", "return_code": 0})
        plan_data_3 = create_plan_data(plan, goal)
        json_3 = json.dumps(plan_data_3, indent=2)

        # Calculate common prefix lengths
        prefixes = []
        json_strings = [json_0, json_1, json_2, json_3]

        for i in range(len(json_strings) - 1):
            current = json_strings[i]
            next_json = json_strings[i + 1]

            # Find common prefix length
            common_len = 0
            for j in range(min(len(current), len(next_json))):
                if current[j] == next_json[j]:
                    common_len += 1
                else:
                    break

            # Calculate prefix percentage
            prefix_percentage = common_len / max(len(current), len(next_json)) * 100
            prefixes.append((i, i+1, common_len, prefix_percentage))

        # Verify that we have reasonable common prefixes for KV-cache benefit
        # The optimization helps most when we have at least some stable prefix
        for iter1, iter2, common_len, percentage in prefixes:
            assert percentage >= 5.0, \
                f"Insufficient common prefix between iteration {iter1} and {iter2}: {percentage:.1f}% (expected ≥5%)"
            assert common_len >= 20, \
                f"Common prefix too short between iteration {iter1} and {iter2}: {common_len} chars (expected ≥20)"

        print(f"✅ KV-cache optimization verified:")
        for iter1, iter2, common_len, percentage in prefixes:
            print(f"  Iteration {iter1}→{iter2}: {common_len} chars ({percentage:.1f}% common)")

    def test_plan_structure_consistency(self):
        """Test that plan structure remains consistent across different scenarios."""
        # Test 1: Empty plan
        empty_plan = Plan(todo=[])
        empty_dict = empty_plan.to_dict()
        assert "completed" in empty_dict
        assert "todo" in empty_dict

        # Test 2: Plan with only completed items
        completed_step = Step("message", {"message": "Task done"}, "Completion message")
        completed_step.result = {"output": "Task completed"}
        completed_step.status = "SUCCESS"

        completed_plan = Plan(todo=[], completed=[completed_step])
        completed_dict = completed_plan.to_dict()

        assert len(completed_dict["completed"]) == 1
        assert len(completed_dict["todo"]) == 0

        # Verify structure order
        keys = list(completed_dict.keys())
        assert keys.index("completed") < keys.index("todo")

    def test_orchestrator_plan_serialization(self):
        """Test that orchestrator plan serialization produces optimized structure."""
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            trace_dir = Path(temp_dir)
            orchestrator = ClayOrchestrator(traces_dir=trace_dir)

            # Create a test plan
            step1 = Step("write", {"file_path": "hello.py", "content": "print('hello')"}, "Create hello file")
            step2 = Step("bash", {"command": "python hello.py"}, "Run hello file")

            plan = Plan(todo=[step1, step2])
            goal = "create and run hello world script"

            # Save plan using orchestrator method
            filepath = orchestrator._save_plan_to_trace_dir(plan, 0, goal)

            # Read and verify the saved plan structure
            with open(filepath, 'r') as f:
                saved_data = json.load(f)

            # Verify optimized structure (no iteration/timestamp at top level)
            assert "goal" in saved_data
            assert "plan" in saved_data
            assert "iteration" not in saved_data  # Removed for KV-cache optimization
            assert "timestamp" not in saved_data  # Removed for KV-cache optimization

            # Verify plan structure has completed before todo
            plan_data = saved_data["plan"]
            keys = list(plan_data.keys())
            assert keys.index("completed") < keys.index("todo")

            print(f"✅ Orchestrator serialization structure verified")
            print(f"  Goal prefix: '{saved_data['goal'][:50]}...'")
            print(f"  Plan keys order: {keys}")

    def test_prefix_optimization_with_realistic_scenario(self):
        """Test prefix optimization with a realistic multi-step coding scenario."""
        goal = "implement a calculator app in python"

        # Create steps that simulate a realistic coding task
        steps = [
            Step("write", {
                "file_path": "calculator.py",
                "content": "class Calculator:\n    def add(self, a, b):\n        return a + b"
            }, "Create main calculator class"),

            Step("write", {
                "file_path": "test_calculator.py",
                "content": "import unittest\nfrom calculator import Calculator"
            }, "Create unit tests"),

            Step("bash", {
                "command": "python -m unittest test_calculator.py"
            }, "Run unit tests"),

            Step("write", {
                "file_path": "main.py",
                "content": "from calculator import Calculator\n\nif __name__ == '__main__':\n    calc = Calculator()"
            }, "Create main application"),

            Step("bash", {
                "command": "python main.py"
            }, "Run the application")
        ]

        plan = Plan(todo=steps)

        # Simulate plan progression through all steps
        plan_states = []

        # Initial state
        plan_data = {"goal": goal, "plan": plan.to_dict()}
        plan_states.append(json.dumps(plan_data, indent=2))

        # Progress through each step
        for i in range(len(steps)):
            # Get the step that's about to be completed (it's always at index 0 in todo)
            current_step = plan.todo[0] if plan.todo else None
            if not current_step:
                break

            # Simulate successful completion with realistic results
            if "write" in current_step.tool_name:
                result = {
                    "output": current_step.parameters.get("content", ""),
                    "file_path": current_step.parameters.get("file_path", ""),
                    "operation": "write"
                }
            else:  # bash command
                result = {
                    "output": "Command completed successfully",
                    "return_code": 0,
                    "command": current_step.parameters.get("command", "")
                }

            plan.complete_next_step(result)
            plan_data = {"goal": goal, "plan": plan.to_dict()}
            plan_states.append(json.dumps(plan_data, indent=2))

        # Analyze prefix stability across all transitions
        min_prefix_percentage = 100.0
        total_transitions = len(plan_states) - 1

        for i in range(total_transitions):
            current = plan_states[i]
            next_state = plan_states[i + 1]

            # Calculate common prefix
            common_len = 0
            for j in range(min(len(current), len(next_state))):
                if current[j] == next_state[j]:
                    common_len += 1
                else:
                    break

            prefix_percentage = common_len / max(len(current), len(next_state)) * 100
            min_prefix_percentage = min(min_prefix_percentage, prefix_percentage)

            print(f"  Step {i}→{i+1}: {common_len} chars ({prefix_percentage:.1f}% common)")

        # Verify reasonable prefix stability throughout the entire progression
        assert min_prefix_percentage >= 4.0, \
            f"Minimum prefix percentage too low: {min_prefix_percentage:.1f}% (expected ≥4%)"

        print(f"✅ Realistic scenario optimization verified:")
        print(f"  Minimum prefix across all transitions: {min_prefix_percentage:.1f}%")
        print(f"  Total plan state transitions: {total_transitions}")

    def test_prefix_progression_improvement(self):
        """Test that prefix stability improves as plan progresses."""
        goal = "create a simple web app"

        # Create a plan with a few steps
        steps = [
            Step("write", {"file_path": "app.py", "content": "from flask import Flask"}, "Create Flask app"),
            Step("write", {"file_path": "requirements.txt", "content": "flask"}, "Create requirements"),
            Step("bash", {"command": "pip install -r requirements.txt"}, "Install dependencies")
        ]

        plan = Plan(todo=steps)

        # Track states as plan progresses
        states = []

        # Initial state
        plan_data = {"goal": goal, "plan": plan.to_dict()}
        states.append(json.dumps(plan_data, indent=2))

        # Progress through steps
        for i in range(len(steps)):
            plan.complete_next_step({"output": f"Step {i+1} completed"})
            plan_data = {"goal": goal, "plan": plan.to_dict()}
            states.append(json.dumps(plan_data, indent=2))

        # Calculate prefix percentages
        prefix_percentages = []
        for i in range(len(states) - 1):
            current = states[i]
            next_state = states[i + 1]

            common_len = 0
            for j in range(min(len(current), len(next_state))):
                if current[j] == next_state[j]:
                    common_len += 1
                else:
                    break

            percentage = common_len / max(len(current), len(next_state)) * 100
            prefix_percentages.append(percentage)

        print(f"✅ Prefix progression analysis:")
        for i, percentage in enumerate(prefix_percentages):
            print(f"  Step {i}→{i+1}: {percentage:.1f}% common prefix")

        # Verify that prefix stability generally improves as plan progresses
        # Later transitions should have higher prefix percentages
        if len(prefix_percentages) > 1:
            # Check that the last transition has better prefix than the first
            improvement = prefix_percentages[-1] - prefix_percentages[0]
            print(f"  Overall improvement: {improvement:.1f} percentage points")
            assert improvement >= 0, \
                f"Prefix stability should improve as plan progresses: {improvement:.1f}"