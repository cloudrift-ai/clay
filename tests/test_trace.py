"""Comprehensive tests for the tracing system."""

import asyncio
import json
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from clay.trace import (
    TraceCollector,
    NestedTraceCall,
    trace_operation,
    trace_method,
    trace_event,
    trace_error,
    trace_llm_call,
    trace_tool_execution,
    trace_agent_action,
    trace_file_operation,
    get_trace_collector,
    save_trace_file,
    clear_trace,
    set_session_id,
    _format_simple_args,
    _get_caller_info
)


class TestTraceCollector:
    """Tests for the TraceCollector class."""

    def test_init(self):
        collector = TraceCollector()
        assert collector._nested_calls == []
        assert collector._call_stacks == {}
        assert collector._session_id is None

    def test_set_session_id(self):
        collector = TraceCollector()
        collector.set_session_id("test_session")
        assert collector._session_id == "test_session"

    def test_clear(self):
        collector = TraceCollector()
        collector.set_session_id("test")

        # Add a call
        call = collector.start_nested_call("test", "operation", {})
        collector.end_nested_call(call, 0.1)

        collector.clear()
        assert collector._nested_calls == []
        assert collector._call_stacks == {}

    def test_nested_call_lifecycle(self):
        collector = TraceCollector()

        # Start a call
        call = collector.start_nested_call("TestComponent", "test_op", {"key": "value"})
        assert len(collector._nested_calls) == 1
        thread_id = str(threading.get_ident())
        assert len(collector._call_stacks[thread_id]) == 1
        assert call.component == "TestComponent"
        assert call.operation == "test_op"
        assert call.details == {"key": "value"}

        # End the call
        collector.end_nested_call(call, 0.5)
        assert thread_id not in collector._call_stacks  # Empty stacks are cleaned up
        assert call.duration == 0.5
        assert call.error is None

    def test_nested_call_with_error(self):
        collector = TraceCollector()

        call = collector.start_nested_call("TestComponent", "test_op", {})
        collector.end_nested_call(call, 0.2, "Test error", "Stack trace")

        assert call.duration == 0.2
        assert call.error == "Test error"
        assert call.stack_trace == "Stack trace"

    def test_nested_calls_hierarchy(self):
        collector = TraceCollector()
        thread_id = str(threading.get_ident())

        # Start parent call
        parent = collector.start_nested_call("Parent", "parent_op", {})
        assert len(collector._nested_calls) == 1
        assert len(collector._call_stacks[thread_id]) == 1

        # Start child call
        child = collector.start_nested_call("Child", "child_op", {})
        assert len(collector._nested_calls) == 1  # Still one top-level call
        assert len(collector._call_stacks[thread_id]) == 2
        assert len(parent.children) == 1
        assert parent.children[0] == child

        # End child call
        collector.end_nested_call(child, 0.1)
        assert len(collector._call_stacks[thread_id]) == 1

        # End parent call
        collector.end_nested_call(parent, 0.3)
        assert thread_id not in collector._call_stacks  # Empty stacks are cleaned up

        # Check hierarchy
        calls = collector.get_nested_calls()
        assert len(calls) == 1
        assert calls[0] == parent
        assert len(calls[0].children) == 1
        assert calls[0].children[0] == child


class TestNestedTraceCall:
    """Tests for the NestedTraceCall dataclass."""

    def test_to_dict(self):
        call = NestedTraceCall(
            timestamp=1234567890.0,
            component="TestComp",
            operation="test_op",
            details={"key": "value"},
            children=[],
            duration=0.5,
            error="Test error",
            stack_trace="Stack trace",
            thread_id="123"
        )

        result = call.to_dict()
        expected_keys = {
            'timestamp', 'timestamp_human', 'component', 'operation',
            'details', 'duration', 'error', 'stack_trace', 'thread_id', 'children'
        }
        assert set(result.keys()) == expected_keys
        assert result['component'] == "TestComp"
        assert result['operation'] == "test_op"
        assert result['details'] == {"key": "value"}
        assert result['duration'] == 0.5
        assert result['error'] == "Test error"
        assert result['children'] == []

    def test_to_dict_with_children(self):
        child = NestedTraceCall(
            timestamp=1234567891.0,
            component="Child",
            operation="child_op",
            details={},
            children=[]
        )

        parent = NestedTraceCall(
            timestamp=1234567890.0,
            component="Parent",
            operation="parent_op",
            details={},
            children=[child]
        )

        result = parent.to_dict()
        assert len(result['children']) == 1
        assert result['children'][0]['component'] == "Child"
        assert result['children'][0]['operation'] == "child_op"


class TestFormatSimpleArgs:
    """Tests for the _format_simple_args function."""

    def test_simple_args(self):
        args = ("hello", 42, 3.14, True, None)
        kwargs = {"name": "test", "count": 5}

        result = _format_simple_args(args, kwargs)
        expected = [
            "arg0='hello'",
            "arg1=42",
            "arg2=3.14",
            "arg3=True",
            "arg4=None",
            "name='test'",
            "count=5"
        ]
        assert result == expected

    def test_skip_self_parameter(self):
        class MockSelf:
            pass

        args = (MockSelf(), "hello", 42)
        kwargs = {}

        result = _format_simple_args(args, kwargs)
        # Should skip the first arg (self)
        expected = ["arg1='hello'", "arg2=42"]
        assert result == expected

    def test_complex_objects(self):
        class CustomClass:
            pass

        args = (CustomClass(), [1, 2, 3], {"key": "value"})
        kwargs = {"obj": CustomClass()}

        result = _format_simple_args(args, kwargs)
        # Should skip first arg (self-like), format list, format dict with length, format kwarg as type
        expected = ["arg1=[1, 2, 3]", "arg2=<dict[1]>", "obj=<CustomClass>"]
        assert result == expected

    def test_long_values(self):
        long_string = "a" * 200
        args = (long_string,)
        kwargs = {}

        result = _format_simple_args(args, kwargs, max_length=50)
        assert len(result[0]) <= 50 + 10  # Account for "arg0='" and truncation
        assert result[0].endswith("...")

    def test_large_collections(self):
        large_list = list(range(20))
        args = (large_list,)
        kwargs = {}

        result = _format_simple_args(args, kwargs)
        # Should show type and length for large collections
        expected = ["arg0=<list[20]>"]
        assert result == expected


class TestGetCallerInfo:
    """Tests for the _get_caller_info function."""

    def test_get_caller_info_basic(self):
        def test_function():
            return _get_caller_info(test_function)

        result = test_function()
        assert 'file' in result
        assert 'line' in result
        assert 'function' in result
        assert result['function'] == 'test_function'
        assert isinstance(result['line'], int)


class TestTraceDecorators:
    """Tests for tracing decorators."""

    def test_trace_operation_sync(self):
        clear_trace()

        @trace_operation
        def test_func(x, y):
            return x + y

        result = test_func(5, 10)
        assert result == 15

        calls = get_trace_collector().get_nested_calls()
        assert len(calls) == 1

        call = calls[0]
        assert call.component == "test_trace"  # Auto-detected from module
        assert call.operation == "test_func"  # Auto-detected from function name
        assert "args" in call.details
        assert call.duration is not None
        assert call.error is None

    def test_trace_operation_with_error(self):
        clear_trace()

        @trace_operation
        def failing_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            failing_func()

        calls = get_trace_collector().get_nested_calls()
        assert len(calls) == 1

        call = calls[0]
        assert call.error == "Test error"
        assert call.stack_trace is not None
        assert "ValueError: Test error" in call.stack_trace

    @pytest.mark.asyncio
    async def test_trace_operation_async(self):
        clear_trace()

        @trace_operation
        async def async_func(value):
            await asyncio.sleep(0.01)
            return value * 2

        result = await async_func(5)
        assert result == 10

        calls = get_trace_collector().get_nested_calls()
        assert len(calls) == 1

        call = calls[0]
        assert call.component == "test_trace"  # Auto-detected from module
        assert call.operation == "async_func"  # Auto-detected from function name
        assert call.duration > 0.01
        assert call.error is None

    def test_trace_method(self):
        clear_trace()

        class TestClass:
            @trace_method()
            def test_method(self, value):
                return value * 3

        obj = TestClass()
        result = obj.test_method(4)
        assert result == 12

        calls = get_trace_collector().get_nested_calls()
        assert len(calls) == 1

        call = calls[0]
        assert call.component == "TestClass"
        assert call.operation == "test_method"
        # Should skip 'self' in args
        assert "arg0=" not in str(call.details.get("args", []))

    def test_nested_trace_operations(self):
        clear_trace()

        @trace_operation
        def parent_func():
            return child_func() + 10

        @trace_operation
        def child_func():
            return 5

        result = parent_func()
        assert result == 15

        calls = get_trace_collector().get_nested_calls()
        assert len(calls) == 1

        parent_call = calls[0]
        assert parent_call.component == "test_trace"  # Auto-detected from module
        assert len(parent_call.children) == 1

        child_call = parent_call.children[0]
        assert child_call.component == "test_trace"  # Auto-detected from module
        assert child_call.operation == "child_func"  # Auto-detected from function name


class TestTraceUtilityFunctions:
    """Tests for utility tracing functions."""

    def test_trace_event(self):
        clear_trace()
        trace_event("TestComp", "test_event", key="value")

        calls = get_trace_collector().get_nested_calls()
        assert len(calls) == 1

        call = calls[0]
        assert call.component == "TestComp"
        assert call.operation == "test_event"
        assert call.details["key"] == "value"
        assert call.duration == 0.0

    def test_trace_error_function(self):
        clear_trace()
        error = ValueError("Test error")
        trace_error("TestComp", "error_op", error, context="test")

        calls = get_trace_collector().get_nested_calls()
        assert len(calls) == 1

        call = calls[0]
        assert call.component == "TestComp"
        assert call.operation == "error_op"
        assert call.error == "Test error"
        assert call.details["context"] == "test"

    def test_trace_llm_call(self):
        clear_trace()
        trace_llm_call("openai", "gpt-4", 1000, temperature=0.7)

        calls = get_trace_collector().get_nested_calls()
        assert len(calls) == 1

        call = calls[0]
        assert call.component == "LLM"
        assert call.operation == "api_call"
        assert call.details["provider"] == "openai"
        assert call.details["model"] == "gpt-4"
        assert call.details["prompt_length"] == 1000
        assert call.details["temperature"] == 0.7

    def test_trace_tool_execution(self):
        clear_trace()
        trace_tool_execution("file_tool", action="read", file="test.py")

        calls = get_trace_collector().get_nested_calls()
        assert len(calls) == 1

        call = calls[0]
        assert call.component == "Tool"
        assert call.operation == "file_tool"
        assert call.details["action"] == "read"
        assert call.details["file"] == "test.py"

    def test_trace_agent_action(self):
        clear_trace()
        trace_agent_action("coding_agent", "generate_code", task="create function")

        calls = get_trace_collector().get_nested_calls()
        assert len(calls) == 1

        call = calls[0]
        assert call.component == "Agent"
        assert call.operation == "generate_code"
        assert call.details["agent"] == "coding_agent"
        assert call.details["task"] == "create function"

    def test_trace_file_operation(self):
        clear_trace()
        trace_file_operation("write", "/path/to/file.py", size=1024)

        calls = get_trace_collector().get_nested_calls()
        assert len(calls) == 1

        call = calls[0]
        assert call.component == "FileSystem"
        assert call.operation == "write"
        assert call.details["filepath"] == "/path/to/file.py"
        assert call.details["size"] == 1024


class TestTraceSerialization:
    """Tests for trace serialization and file operations."""

    def test_save_trace_file(self):
        clear_trace()
        set_session_id("test_session")

        # Create some trace data
        trace_event("TestComp", "test_op", data="test")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            filepath = save_trace_file("test_session", output_dir)

            assert filepath.exists()
            assert "test_session" in filepath.name
            assert filepath.suffix == ".json"

            # Verify content
            with open(filepath) as f:
                data = json.load(f)

            assert data["session_id"] == "test_session"
            assert "start_time" in data
            assert "end_time" in data
            assert "call_stack" in data
            assert len(data["call_stack"]) == 1
            assert data["call_stack"][0]["component"] == "TestComp"

    def test_collector_save_to_file(self):
        collector = TraceCollector()
        collector.set_session_id("test_session")

        # Add a nested call
        call = collector.start_nested_call("TestComp", "test_op", {"key": "value"})
        collector.end_nested_call(call, 0.5)

        with tempfile.TemporaryDirectory() as temp_dir:
            filepath = Path(temp_dir) / "test_trace.json"
            collector.save_to_file(filepath)

            assert filepath.exists()

            with open(filepath) as f:
                data = json.load(f)

            assert data["session_id"] == "test_session"
            assert len(data["call_stack"]) == 1
            assert data["call_stack"][0]["component"] == "TestComp"
            assert data["call_stack"][0]["duration"] == 0.5


class TestComplexScenarios:
    """Tests for complex tracing scenarios."""

    @pytest.mark.asyncio
    async def test_mixed_sync_async_tracing(self):
        clear_trace()

        @trace_operation
        def sync_func():
            return "sync_result"

        @trace_operation
        async def async_func():
            # Call sync function from async context
            sync_result = sync_func()
            await asyncio.sleep(0.01)
            return f"async_{sync_result}"

        result = await async_func()
        assert result == "async_sync_result"

        calls = get_trace_collector().get_nested_calls()
        assert len(calls) == 1

        async_call = calls[0]
        assert async_call.component == "test_trace"  # Auto-detected from module
        assert len(async_call.children) == 1

        sync_call = async_call.children[0]
        assert sync_call.component == "test_trace"  # Auto-detected from module

    def test_deep_nesting(self):
        clear_trace()

        @trace_operation
        def level1():
            return level2() + 1

        @trace_operation
        def level2():
            return level3() + 1

        @trace_operation
        def level3():
            return 1

        result = level1()
        assert result == 3

        calls = get_trace_collector().get_nested_calls()
        assert len(calls) == 1

        # Check nesting structure
        l1 = calls[0]
        assert l1.component == "test_trace"  # Auto-detected from module
        assert l1.operation == "level1"  # Auto-detected from function name
        assert len(l1.children) == 1

        l2 = l1.children[0]
        assert l2.component == "test_trace"  # Auto-detected from module
        assert l2.operation == "level2"  # Auto-detected from function name
        assert len(l2.children) == 1

        l3 = l2.children[0]
        assert l3.component == "test_trace"  # Auto-detected from module
        assert l3.operation == "level3"  # Auto-detected from function name
        assert len(l3.children) == 0

    def test_error_propagation_in_nesting(self):
        clear_trace()

        @trace_operation
        def parent_func():
            return child_func()

        @trace_operation
        def child_func():
            raise RuntimeError("Child error")

        with pytest.raises(RuntimeError, match="Child error"):
            parent_func()

        calls = get_trace_collector().get_nested_calls()
        assert len(calls) == 1

        parent_call = calls[0]
        assert parent_call.error == "Child error"
        assert len(parent_call.children) == 1

        child_call = parent_call.children[0]
        assert child_call.error == "Child error"
        assert "RuntimeError: Child error" in child_call.stack_trace

    def test_concurrent_tracing(self):
        """Test that tracing works correctly with concurrent execution."""
        import threading
        clear_trace()

        results = []

        @trace_operation
        def thread_func(thread_id):
            time.sleep(0.01)  # Small delay to ensure overlap
            results.append(f"thread_{thread_id}")
            return thread_id

        threads = []
        for i in range(3):
            t = threading.Thread(target=thread_func, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        calls = get_trace_collector().get_nested_calls()
        assert len(calls) == 3

        # Verify all threads were traced
        thread_ids = set()
        for call in calls:
            assert call.component == "test_trace"  # Auto-detected from module
            assert call.operation == "thread_func"  # Auto-detected from function name
            thread_ids.add(call.thread_id)

        # Should have 3 different thread IDs
        assert len(thread_ids) == 3