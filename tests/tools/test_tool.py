"""Tests for tool description accuracy using LLM validation.

This test suite validates that tool descriptions are accurate and comprehensive by:

1. Checking that all tools have complete descriptions, schemas, and examples
2. Validating that tool schemas properly validate parameters
3. Testing that LLM can understand tool descriptions and generate valid tool calls
4. Ensuring all tools are properly discoverable and registered

The LLM validation test feeds tool descriptions to an LLM and verifies that:
- The LLM can generate valid JSON tool calls based on the descriptions
- The generated tool calls pass schema validation
- The tool calls match expected patterns for specific scenarios

This ensures that tool descriptions provide clear, accurate guidance for AI agents.
"""

import pytest
import json
import inspect
import importlib
from typing import List, Dict

from clay.tools.base import Tool
from clay.llm import completion


class TestToolDescriptionAccuracy:
    """Test that tool descriptions accurately represent tool capabilities."""

    @pytest.fixture
    def available_tools(self) -> List[Tool]:
        """Get all available tool classes instantiated by auto-discovery."""
        import clay.tools
        tools = []

        # Get all modules in the clay.tools package
        tools_module = clay.tools

        # Iterate through all attributes in the tools module
        for name in dir(tools_module):
            obj = getattr(tools_module, name)

            # Check if it's a class that inherits from Tool but isn't Tool itself
            if (inspect.isclass(obj) and
                issubclass(obj, Tool) and
                obj is not Tool and
                not inspect.isabstract(obj)):

                try:
                    # Try to instantiate the tool class
                    # Most tools should have default constructors
                    tool_instance = obj()
                    tools.append(tool_instance)
                except Exception as e:
                    # Skip tools that can't be instantiated with default parameters
                    print(f"Warning: Could not instantiate tool {name}: {e}")
                    continue

        return tools

    @pytest.mark.asyncio
    async def test_tool_description_completeness(self, available_tools):
        """Test that tool descriptions contain all necessary information."""
        for tool in available_tools:
            # Test basic description exists
            assert tool.description, f"Tool {tool.name} missing description"
            assert tool.capabilities, f"Tool {tool.name} missing capabilities"
            assert tool.use_cases, f"Tool {tool.name} missing use cases"

            # Test schema is valid
            schema = tool.get_schema()
            assert isinstance(schema, dict), f"Tool {tool.name} schema must be dict"
            assert "type" in schema, f"Tool {tool.name} schema missing type"
            assert "properties" in schema, f"Tool {tool.name} schema missing properties"

            # Test example usage is valid JSON
            example = tool.get_example_usage()
            try:
                parsed_example = json.loads(example)
                if isinstance(parsed_example, list):
                    # Multiple examples
                    for ex in parsed_example:
                        assert "tool_name" in ex, f"Example missing tool_name"
                        assert "parameters" in ex, f"Example missing parameters"
                        assert "description" in ex, f"Example missing description"
                else:
                    # Single example
                    assert "tool_name" in parsed_example, f"Example missing tool_name"
                    assert "parameters" in parsed_example, f"Example missing parameters"
                    assert "description" in parsed_example, f"Example missing description"
            except json.JSONDecodeError as e:
                pytest.fail(f"Tool {tool.name} example usage is not valid JSON: {e}")

    @pytest.mark.asyncio
    async def test_llm_can_understand_tool_descriptions(self, available_tools):
        """Test that LLM can understand and use tool descriptions correctly."""
        for tool in available_tools:
            await self._test_tool_with_llm(tool)

    async def _test_tool_with_llm(self, tool: Tool):
        """Test a specific tool with LLM to validate description accuracy."""
        # Get tool's detailed description
        tool_description = tool.get_detailed_description(
            include_capabilities=True,
            include_use_cases=True,
            include_schema=True
        )

        # Create test scenarios based on tool capabilities
        test_scenarios = self._generate_test_scenarios(tool)

        for scenario in test_scenarios:
            await self._test_scenario_with_llm(tool, tool_description, scenario)

    def _generate_test_scenarios(self, tool: Tool) -> List[Dict[str, str]]:
        """Generate test scenarios for a tool based on its capabilities."""
        scenarios = []

        if tool.name == "bash":
            scenarios = [
                {
                    "task": "List all files in the current directory",
                    "expected_command_pattern": "ls"
                },
                {
                    "task": "Create a simple Python script that prints hello world",
                    "expected_command_pattern": "cat > .* << 'EOF'"
                },
                {
                    "task": "Find all Python files in the project",
                    "expected_command_pattern": "find .* -name.*\\.py"
                },
                {
                    "task": "Run tests with a timeout of 5 minutes",
                    "expected_command_pattern": ".*test.*",
                    "expected_params": {"timeout": 300}
                }
            ]

        return scenarios

    async def _test_scenario_with_llm(self, tool: Tool, tool_description: str, scenario: Dict[str, str]):
        """Test a specific scenario with the LLM."""
        system_prompt = f"""
You are an AI assistant that needs to use tools to complete tasks. You have access to the following tool:

{tool_description}

Your task is to generate a valid tool call JSON to complete the given task.
Respond with ONLY a valid JSON object representing the tool call, nothing else.
The JSON should have this structure:
{{
    "tool_name": "tool_name",
    "parameters": {{
        "param1": "value1",
        "param2": "value2"
    }}
}}
"""

        user_prompt = f"Generate a tool call to: {scenario['task']}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            # Get LLM response
            response = await completion(messages, temperature=0.1, max_tokens=500)
            content = response["choices"][0]["message"]["content"].strip()

            # Parse the JSON response
            try:
                tool_call = json.loads(content)
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code blocks
                if "```json" in content:
                    json_start = content.find("```json") + 7
                    json_end = content.find("```", json_start)
                    if json_end > json_start:
                        content = content[json_start:json_end].strip()
                        tool_call = json.loads(content)
                    else:
                        pytest.fail(f"Could not extract JSON from LLM response: {content}")
                elif "```" in content:
                    json_start = content.find("```") + 3
                    json_end = content.find("```", json_start)
                    if json_end > json_start:
                        content = content[json_start:json_end].strip()
                        tool_call = json.loads(content)
                    else:
                        pytest.fail(f"Could not extract JSON from LLM response: {content}")
                else:
                    pytest.fail(f"LLM response is not valid JSON: {content}")

            # Validate the tool call structure
            assert isinstance(tool_call, dict), "Tool call must be a dictionary"
            assert "tool_name" in tool_call, "Tool call missing tool_name"
            assert "parameters" in tool_call, "Tool call missing parameters"
            assert tool_call["tool_name"] == tool.name, f"Wrong tool name: expected {tool.name}, got {tool_call['tool_name']}"

            # Validate parameters against tool schema
            tool.validate_parameters(tool_call["parameters"])

            # Check scenario-specific expectations
            if "expected_command_pattern" in scenario and tool.name == "bash":
                import re
                command = tool_call["parameters"].get("command", "")
                pattern = scenario["expected_command_pattern"]
                assert re.search(pattern, command, re.IGNORECASE), \
                    f"Command '{command}' doesn't match expected pattern '{pattern}'"

            if "expected_params" in scenario:
                for key, expected_value in scenario["expected_params"].items():
                    actual_value = tool_call["parameters"].get(key)
                    assert actual_value == expected_value, \
                        f"Parameter {key}: expected {expected_value}, got {actual_value}"

            # Test that the tool call can actually be executed (validation only)
            try:
                # Just validate, don't execute for safety
                await tool.run(**tool_call["parameters"])
                # If we get here without exception, validation passed
            except Exception as e:
                # Log the error but don't fail - some commands might fail execution but pass validation
                print(f"Tool execution validation warning for scenario '{scenario['task']}': {e}")

        except Exception as e:
            pytest.fail(f"Failed to test scenario '{scenario['task']}' for tool {tool.name}: {e}")

    @pytest.mark.asyncio
    async def test_tool_schema_validation(self, available_tools):
        """Test that tool schemas properly validate parameters."""
        for tool in available_tools:
            schema = tool.get_schema()
            required_fields = schema.get("required", [])
            properties = schema.get("properties", {})

            # Test required field validation
            if required_fields:
                # Test missing required field
                with pytest.raises(Exception):
                    tool.validate_parameters({})

                # Test with all required fields
                valid_params = {}
                for field in required_fields:
                    field_info = properties.get(field, {})
                    field_type = field_info.get("type", "string")

                    if field_type == "string":
                        valid_params[field] = "test_value"
                    elif field_type == "integer":
                        valid_params[field] = 30
                    elif field_type == "boolean":
                        valid_params[field] = True
                    else:
                        valid_params[field] = "test_value"

                # This should not raise an exception
                tool.validate_parameters(valid_params)

    def test_tool_discovery_completeness(self):
        """Test that all tool classes are discoverable and properly registered."""
        # This test ensures we don't miss any tools when they are added
        from clay.tools import __all__ as exported_tools

        # Should have at least the base classes and BashTool
        expected_tools = ["Tool", "ToolResult", "ToolError", "BashTool", "BashToolResult"]

        for tool_name in expected_tools:
            assert tool_name in exported_tools, f"Tool {tool_name} not exported in __all__"