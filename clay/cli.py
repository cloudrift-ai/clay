"""CLI interface for Clay."""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional

from clay.orchestrator import ClayOrchestrator, Plan
from clay.trace import clear_trace, set_session_id


async def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Clay - An agentic coding system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  clay                                           # Start interactive REPL mode
  clay "create a hello world python script"     # Execute a single task
  clay "fix the bug in main.py" --no-interactive # Execute without agent input prompts
  clay --traces-dir ./my_traces                 # Interactive mode with custom traces
        """
    )

    parser.add_argument('task', nargs='*', help='The task to execute (if not provided, starts interactive mode)')
    parser.add_argument('--interactive', action='store_true', default=None,
                       help='Enable interactive mode, prompting for user input (default)')
    parser.add_argument('--traces-dir', type=Path,
                       help='Directory to save traces (default: ./traces)')

    # Parse arguments
    args = parser.parse_args()

    orchestrator = ClayOrchestrator(traces_dir=args.traces_dir)
    plan = Plan()
    if len(args.task) > 0:
        plan = orchestrator.create_plan_from_goal(" ".join(args.task))

    interactive = args.interactive
    if interactive is None:
        interactive = len(args.task) == 0  # Default to interactive if no task provided

    clear_trace()
    set_session_id("session")

    # Create plan from task goal if provided, otherwise run interactive mode
    if interactive:
        await orchestrator.process_task_interactive(plan, session_id="session")
    else:
        await orchestrator.process_task(plan, session_id="session")


def start():
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
