"""Comprehensive tracing system for Clay execution."""

import json
import os
import time
import threading
import traceback
import inspect
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from dataclasses import dataclass
from functools import wraps



def _get_caller_info(func):
    """Get file path, line number, and function name for a function."""
    try:
        frame = inspect.currentframe()
        # Go up the stack to find the calling frame
        # Skip: _get_caller_info -> decorator wrapper -> actual function
        while frame and frame.f_code.co_name in ['_get_caller_info', 'wrapper', 'async_wrapper']:
            frame = frame.f_back

        if frame:
            filename = frame.f_code.co_filename
            # Make path relative to project root if possible
            try:
                rel_path = os.path.relpath(filename, os.getcwd())
                if not rel_path.startswith('..'):
                    filename = rel_path
            except ValueError:
                pass  # Keep absolute path if relpath fails

            return {
                'file': filename,
                'line': frame.f_lineno,
                'function': func.__name__
            }
    except Exception:
        pass

    # Fallback to function info only
    return {
        'file': getattr(func, '__module__', 'unknown'),
        'line': None,
        'function': func.__name__
    }


def _format_simple_args(args, kwargs, max_length=100):
    """Format simple argument values for tracing, avoiding complex objects."""
    formatted_args = []

    # Format positional args (skip 'self' if present)
    # Check if first arg looks like a 'self' parameter (has __class__ but isn't a simple type)
    start_idx = 0
    if (args and hasattr(args[0], '__class__') and
        not isinstance(args[0], (str, int, float, bool, type(None), list, tuple, dict))):
        start_idx = 1

    for i, arg in enumerate(args[start_idx:]):
        try:
            actual_index = i + start_idx
            if isinstance(arg, (str, int, float, bool, type(None))):
                arg_str = repr(arg)
                if len(arg_str) > max_length:
                    arg_str = arg_str[:max_length-3] + "..."
                formatted_args.append(f"arg{actual_index}={arg_str}")
            elif isinstance(arg, (list, tuple)) and len(arg) < 10:
                # Include small collections if they contain simple types
                if all(isinstance(item, (str, int, float, bool, type(None))) for item in arg):
                    arg_str = repr(arg)
                    if len(arg_str) > max_length:
                        arg_str = arg_str[:max_length-3] + "..."
                    formatted_args.append(f"arg{actual_index}={arg_str}")
                else:
                    formatted_args.append(f"arg{actual_index}=<{type(arg).__name__}[{len(arg)}]>")
            else:
                # For complex objects, just show type and basic info
                if hasattr(arg, '__len__'):
                    try:
                        length = len(arg)
                        formatted_args.append(f"arg{actual_index}=<{type(arg).__name__}[{length}]>")
                    except (TypeError, AttributeError):
                        formatted_args.append(f"arg{actual_index}=<{type(arg).__name__}>")
                else:
                    formatted_args.append(f"arg{actual_index}=<{type(arg).__name__}>")
        except Exception:
            formatted_args.append(f"arg{actual_index}=<unprintable>")

    # Format keyword args
    for key, value in kwargs.items():
        try:
            if isinstance(value, (str, int, float, bool, type(None))):
                val_str = repr(value)
                if len(val_str) > max_length:
                    val_str = val_str[:max_length-3] + "..."
                formatted_args.append(f"{key}={val_str}")
            elif isinstance(value, (list, tuple)) and len(value) < 10:
                # Include small collections if they contain simple types
                if all(isinstance(item, (str, int, float, bool, type(None))) for item in value):
                    val_str = repr(value)
                    if len(val_str) > max_length:
                        val_str = val_str[:max_length-3] + "..."
                    formatted_args.append(f"{key}={val_str}")
                else:
                    formatted_args.append(f"{key}=<{type(value).__name__}[{len(value)}]>")
            else:
                # For complex objects, just show type
                if hasattr(value, '__len__'):
                    try:
                        length = len(value)
                        formatted_args.append(f"{key}=<{type(value).__name__}[{length}]>")
                    except (TypeError, AttributeError):
                        formatted_args.append(f"{key}=<{type(value).__name__}>")
                else:
                    formatted_args.append(f"{key}=<{type(value).__name__}>")
        except Exception:
            formatted_args.append(f"{key}=<unprintable>")

    return formatted_args


@dataclass
class TraceEvent:
    """Single trace event."""
    timestamp: float
    event_type: str
    component: str
    operation: str
    details: Dict[str, Any]
    duration: Optional[float] = None
    error: Optional[str] = None
    stack_trace: Optional[str] = None
    thread_id: str = ""

    def __post_init__(self):
        if not self.thread_id:
            self.thread_id = str(threading.get_ident())


@dataclass
class NestedTraceCall:
    """Represents a nested function call with timing and children."""
    timestamp: float
    component: str
    operation: str
    details: Dict[str, Any]
    children: List['NestedTraceCall']
    duration: Optional[float] = None
    error: Optional[str] = None
    stack_trace: Optional[str] = None
    thread_id: str = ""

    def __post_init__(self):
        if not self.thread_id:
            self.thread_id = str(threading.get_ident())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'timestamp': self.timestamp,
            'timestamp_human': datetime.fromtimestamp(self.timestamp).isoformat(),
            'component': self.component,
            'operation': self.operation,
            'details': self.details,
            'duration': self.duration,
            'error': self.error,
            'stack_trace': self.stack_trace,
            'thread_id': self.thread_id,
            'children': [child.to_dict() for child in self.children]
        }


class TraceCollector:
    """Thread-safe trace event collector with call stack tracking."""

    def __init__(self):
        self._nested_calls: List[NestedTraceCall] = []
        self._call_stacks: Dict[str, List[NestedTraceCall]] = {}  # Per-thread call stacks
        self._lock = threading.Lock()
        self._session_id: Optional[str] = None
        self._start_time = time.time()

    def set_session_id(self, session_id: str):
        """Set the session ID for this trace."""
        self._session_id = session_id

    def clear(self):
        """Clear all events."""
        with self._lock:
            self._nested_calls.clear()
            self._call_stacks.clear()
            self._start_time = time.time()

    def start_nested_call(self, component: str, operation: str, details: Dict[str, Any]) -> NestedTraceCall:
        """Start a new nested call and push to stack."""
        thread_id = str(threading.get_ident())

        with self._lock:
            call = NestedTraceCall(
                timestamp=time.time(),
                component=component,
                operation=operation,
                details=details,
                children=[]
            )

            # Get or create call stack for this thread
            if thread_id not in self._call_stacks:
                self._call_stacks[thread_id] = []
            call_stack = self._call_stacks[thread_id]

            if call_stack:
                # Add as child to current call in this thread's stack
                call_stack[-1].children.append(call)
            else:
                # This is a top-level call for this thread
                self._nested_calls.append(call)

            # Push to thread's stack
            call_stack.append(call)
            return call

    def end_nested_call(self, call: NestedTraceCall, duration: float, error: str = None, stack_trace: str = None):
        """End a nested call and pop from stack."""
        thread_id = str(threading.get_ident())

        with self._lock:
            if thread_id in self._call_stacks:
                call_stack = self._call_stacks[thread_id]
                if call_stack and call_stack[-1] == call:
                    call.duration = duration
                    call.error = error
                    call.stack_trace = stack_trace
                    call_stack.pop()

                    # Clean up empty call stack
                    if not call_stack:
                        del self._call_stacks[thread_id]

    def get_nested_calls(self) -> List[NestedTraceCall]:
        """Get all top-level nested calls."""
        with self._lock:
            return self._nested_calls.copy()

    def get_events(self) -> List[NestedTraceCall]:
        """Get all nested calls (compatibility method)."""
        return self.get_nested_calls()

    def save_to_file(self, filepath: Path):
        """Save nested calls to JSON file."""
        nested_calls_data = []

        with self._lock:
            # Process nested calls
            for call in self._nested_calls:
                nested_calls_data.append(call.to_dict())

        trace_data = {
            'session_id': self._session_id,
            'start_time': self._start_time,
            'start_time_human': datetime.fromtimestamp(self._start_time).isoformat(),
            'end_time': time.time(),
            'end_time_human': datetime.now().isoformat(),
            'total_calls': len(nested_calls_data),
            'call_stack': nested_calls_data  # Nested structure showing call hierarchy
        }

        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(trace_data, f, indent=2, default=str)


# Global trace collector
_trace_collector = TraceCollector()


def get_trace_collector() -> TraceCollector:
    """Get the global trace collector."""
    return _trace_collector



def trace_operation(func=None, **details):
    """Decorator for tracing operations with duration.

    Can be used as @trace_operation or @trace_operation(extra="data")
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get caller information
            caller_info = _get_caller_info(func)
            formatted_args = _format_simple_args(args, kwargs)
            enhanced_details = {
                **details,
                **caller_info,
                'args': formatted_args,
                'arg_count': len(args),
                'kwarg_count': len(kwargs)
            }

            # Auto-detect component from module or class
            component = func.__module__
            if (args and hasattr(args[0], '__class__') and
                not isinstance(args[0], (str, int, float, bool, type(None), list, tuple, dict)) and
                hasattr(args[0].__class__, '__name__')):
                # If first argument is 'self' (an object instance), use class name as component
                component = args[0].__class__.__name__
            elif '.' in component:
                # Use last part of module path
                component = component.split('.')[-1]

            operation = func.__name__

            start_time = time.time()
            nested_call = _trace_collector.start_nested_call(component, operation, enhanced_details)

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                _trace_collector.end_nested_call(nested_call, duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                _trace_collector.end_nested_call(nested_call, duration, str(e), traceback.format_exc())
                raise

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get caller information
            caller_info = _get_caller_info(func)
            formatted_args = _format_simple_args(args, kwargs)
            enhanced_details = {
                **details,
                **caller_info,
                'args': formatted_args,
                'arg_count': len(args),
                'kwarg_count': len(kwargs)
            }

            # Auto-detect component from module or class
            component = func.__module__
            if (args and hasattr(args[0], '__class__') and
                not isinstance(args[0], (str, int, float, bool, type(None), list, tuple, dict)) and
                hasattr(args[0].__class__, '__name__')):
                # If first argument is 'self' (an object instance), use class name as component
                component = args[0].__class__.__name__
            elif '.' in component:
                # Use last part of module path
                component = component.split('.')[-1]

            operation = func.__name__

            start_time = time.time()
            nested_call = _trace_collector.start_nested_call(component, operation, enhanced_details)

            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                _trace_collector.end_nested_call(nested_call, duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                _trace_collector.end_nested_call(nested_call, duration, str(e), traceback.format_exc())
                raise

        # Return appropriate wrapper based on whether function is async
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper

    # Handle both @trace_operation and @trace_operation() patterns
    if func is None:
        # Called with parentheses: @trace_operation() or @trace_operation(extra="data")
        return decorator
    else:
        # Called without parentheses: @trace_operation
        return decorator(func)


def trace_method(component: str = None):
    """Decorator to trace method calls."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Determine component name
            comp = component
            if not comp and args and hasattr(args[0], '__class__'):
                comp = args[0].__class__.__name__
            elif not comp:
                comp = func.__module__

            start_time = time.time()

            # Get caller information
            caller_info = _get_caller_info(func)

            # Format arguments
            formatted_args = _format_simple_args(args, kwargs)

            # Extract method details with enhanced information
            method_details = {
                **caller_info,
                'args': formatted_args,
                'arg_count': len(args),
                'kwarg_count': len(kwargs)
            }

            # Start nested call tracking
            nested_call = _trace_collector.start_nested_call(comp, func.__name__, method_details)

            try:
                result = func(*args, **kwargs)

                # Record success
                duration = time.time() - start_time
                _trace_collector.end_nested_call(nested_call, duration)
                return result

            except Exception as e:
                # Record error
                duration = time.time() - start_time
                _trace_collector.end_nested_call(nested_call, duration, str(e), traceback.format_exc())
                raise

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Determine component name
            comp = component
            if not comp and args and hasattr(args[0], '__class__'):
                comp = args[0].__class__.__name__
            elif not comp:
                comp = func.__module__

            start_time = time.time()

            # Get caller information
            caller_info = _get_caller_info(func)

            # Format arguments
            formatted_args = _format_simple_args(args, kwargs)

            # Extract method details with enhanced information
            method_details = {
                **caller_info,
                'args': formatted_args,
                'arg_count': len(args),
                'kwarg_count': len(kwargs)
            }

            # Start nested call tracking
            nested_call = _trace_collector.start_nested_call(comp, func.__name__, method_details)

            try:
                result = await func(*args, **kwargs)

                # Record success
                duration = time.time() - start_time
                _trace_collector.end_nested_call(nested_call, duration)
                return result

            except Exception as e:
                # Record error
                duration = time.time() - start_time
                _trace_collector.end_nested_call(nested_call, duration, str(e), traceback.format_exc())
                raise

        # Return appropriate wrapper based on whether function is async
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper

    return decorator


def save_trace_file(session_id: str = None, output_dir: Path = None) -> Path:
    """Save trace to file and return the filepath."""
    if output_dir is None:
        # Use current working directory - for tests this will be the isolated test directory
        output_dir = Path.cwd() / "_traces"

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"clay_trace_{timestamp}"
    if session_id:
        filename += f"_{session_id}"
    filename += ".json"

    filepath = output_dir / filename
    _trace_collector.save_to_file(filepath)
    return filepath


def clear_trace():
    """Clear all trace events."""
    _trace_collector.clear()


def set_session_id(session_id: str):
    """Set session ID for tracing."""
    _trace_collector.set_session_id(session_id)


