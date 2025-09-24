"""Comprehensive tracing system for Clay execution."""

import json
import os
import time
import threading
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from dataclasses import dataclass, asdict
from functools import wraps


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


class TraceCollector:
    """Thread-safe trace event collector."""

    def __init__(self):
        self._events: List[TraceEvent] = []
        self._lock = threading.Lock()
        self._session_id: Optional[str] = None
        self._start_time = time.time()

    def set_session_id(self, session_id: str):
        """Set the session ID for this trace."""
        self._session_id = session_id

    def add_event(self, event: TraceEvent):
        """Add a trace event."""
        with self._lock:
            self._events.append(event)

    def get_events(self) -> List[TraceEvent]:
        """Get all trace events."""
        with self._lock:
            return self._events.copy()

    def clear(self):
        """Clear all events."""
        with self._lock:
            self._events.clear()
            self._start_time = time.time()

    def save_to_file(self, filepath: Path):
        """Save trace events to JSON file."""
        events_data = []
        with self._lock:
            for event in self._events:
                event_dict = asdict(event)
                # Convert timestamp to readable format
                event_dict['timestamp_human'] = datetime.fromtimestamp(event.timestamp).isoformat()
                events_data.append(event_dict)

        trace_data = {
            'session_id': self._session_id,
            'start_time': self._start_time,
            'start_time_human': datetime.fromtimestamp(self._start_time).isoformat(),
            'end_time': time.time(),
            'end_time_human': datetime.now().isoformat(),
            'total_events': len(events_data),
            'events': events_data
        }

        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(trace_data, f, indent=2, default=str)


# Global trace collector
_trace_collector = TraceCollector()


def get_trace_collector() -> TraceCollector:
    """Get the global trace collector."""
    return _trace_collector


def trace_event(component: str, operation: str, **details):
    """Record a trace event."""
    event = TraceEvent(
        timestamp=time.time(),
        event_type="event",
        component=component,
        operation=operation,
        details=details
    )
    _trace_collector.add_event(event)


def trace_error(component: str, operation: str, error: Exception, **details):
    """Record a trace error event."""
    event = TraceEvent(
        timestamp=time.time(),
        event_type="error",
        component=component,
        operation=operation,
        details=details,
        error=str(error),
        stack_trace=traceback.format_exc()
    )
    _trace_collector.add_event(event)


def trace_operation(component: str, operation: str, **details):
    """Decorator for tracing operations with duration."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()

            # Record start event
            start_event = TraceEvent(
                timestamp=start_time,
                event_type="operation_start",
                component=component,
                operation=operation,
                details=details
            )
            _trace_collector.add_event(start_event)

            try:
                result = func(*args, **kwargs)

                # Record success end event
                duration = time.time() - start_time
                end_event = TraceEvent(
                    timestamp=time.time(),
                    event_type="operation_end",
                    component=component,
                    operation=operation,
                    details={**details, "status": "success"},
                    duration=duration
                )
                _trace_collector.add_event(end_event)
                return result

            except Exception as e:
                # Record error end event
                duration = time.time() - start_time
                end_event = TraceEvent(
                    timestamp=time.time(),
                    event_type="operation_end",
                    component=component,
                    operation=operation,
                    details={**details, "status": "error"},
                    duration=duration,
                    error=str(e),
                    stack_trace=traceback.format_exc()
                )
                _trace_collector.add_event(end_event)
                raise

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()

            # Record start event
            start_event = TraceEvent(
                timestamp=start_time,
                event_type="operation_start",
                component=component,
                operation=operation,
                details=details
            )
            _trace_collector.add_event(start_event)

            try:
                result = await func(*args, **kwargs)

                # Record success end event
                duration = time.time() - start_time
                end_event = TraceEvent(
                    timestamp=time.time(),
                    event_type="operation_end",
                    component=component,
                    operation=operation,
                    details={**details, "status": "success"},
                    duration=duration
                )
                _trace_collector.add_event(end_event)
                return result

            except Exception as e:
                # Record error end event
                duration = time.time() - start_time
                end_event = TraceEvent(
                    timestamp=time.time(),
                    event_type="operation_end",
                    component=component,
                    operation=operation,
                    details={**details, "status": "error"},
                    duration=duration,
                    error=str(e),
                    stack_trace=traceback.format_exc()
                )
                _trace_collector.add_event(end_event)
                raise

        # Return appropriate wrapper based on whether function is async
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper

    return decorator


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

            # Extract method details
            method_details = {
                "function": func.__name__,
                "args_count": len(args),
                "kwargs": list(kwargs.keys())
            }

            start_time = time.time()

            # Record start event
            start_event = TraceEvent(
                timestamp=start_time,
                event_type="operation_start",
                component=comp,
                operation=func.__name__,
                details=method_details
            )
            _trace_collector.add_event(start_event)

            try:
                result = func(*args, **kwargs)

                # Record success end event
                duration = time.time() - start_time
                end_event = TraceEvent(
                    timestamp=time.time(),
                    event_type="operation_end",
                    component=comp,
                    operation=func.__name__,
                    details={**method_details, "status": "success"},
                    duration=duration
                )
                _trace_collector.add_event(end_event)
                return result

            except Exception as e:
                # Record error end event
                duration = time.time() - start_time
                end_event = TraceEvent(
                    timestamp=time.time(),
                    event_type="operation_end",
                    component=comp,
                    operation=func.__name__,
                    details={**method_details, "status": "error"},
                    duration=duration,
                    error=str(e),
                    stack_trace=traceback.format_exc()
                )
                _trace_collector.add_event(end_event)
                raise

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Determine component name
            comp = component
            if not comp and args and hasattr(args[0], '__class__'):
                comp = args[0].__class__.__name__
            elif not comp:
                comp = func.__module__

            # Extract method details
            method_details = {
                "function": func.__name__,
                "args_count": len(args),
                "kwargs": list(kwargs.keys())
            }

            start_time = time.time()

            # Record start event
            start_event = TraceEvent(
                timestamp=start_time,
                event_type="operation_start",
                component=comp,
                operation=func.__name__,
                details=method_details
            )
            _trace_collector.add_event(start_event)

            try:
                result = await func(*args, **kwargs)

                # Record success end event
                duration = time.time() - start_time
                end_event = TraceEvent(
                    timestamp=time.time(),
                    event_type="operation_end",
                    component=comp,
                    operation=func.__name__,
                    details={**method_details, "status": "success"},
                    duration=duration
                )
                _trace_collector.add_event(end_event)
                return result

            except Exception as e:
                # Record error end event
                duration = time.time() - start_time
                end_event = TraceEvent(
                    timestamp=time.time(),
                    event_type="operation_end",
                    component=comp,
                    operation=func.__name__,
                    details={**method_details, "status": "error"},
                    duration=duration,
                    error=str(e),
                    stack_trace=traceback.format_exc()
                )
                _trace_collector.add_event(end_event)
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
        output_dir = Path.cwd() / "traces"

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


# Utility functions for common trace patterns
def trace_llm_call(provider: str, model: str, prompt_length: int, **details):
    """Trace LLM API call."""
    trace_event("LLM", "api_call",
                provider=provider,
                model=model,
                prompt_length=prompt_length,
                **details)


def trace_tool_execution(tool_name: str, **details):
    """Trace tool execution."""
    trace_event("Tool", tool_name, **details)


def trace_agent_action(agent_name: str, action: str, **details):
    """Trace agent action."""
    trace_event("Agent", action, agent=agent_name, **details)


def trace_file_operation(operation: str, filepath: str, **details):
    """Trace file operations."""
    trace_event("FileSystem", operation, filepath=filepath, **details)