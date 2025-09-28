"""CLI interface for Clay."""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional

from clay.orchestrator.orchestrator import ClayOrchestrator


async def execute_task(task: Optional[str], interactive: bool = True, traces_dir: Path = None):
    """Execute a task with Clay. If task is None, starts interactive REPL mode."""
    if traces_dir is None:
        traces_dir = Path("traces")
        traces_dir.mkdir(exist_ok=True)

    try:
        # Execute the task (or start REPL if task is None) with automatic trace saving and interactive mode
        orchestrator = ClayOrchestrator(traces_dir=traces_dir, interactive=interactive)
        await orchestrator.process_task(task)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)



def main():
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
    parser.add_argument('--no-interactive', action='store_true',
                       help='Disable interactive mode (no user prompts during execution)')
    parser.add_argument('--traces-dir', type=Path,
                       help='Directory to save traces (default: ./traces)')

    # Parse arguments
    args = parser.parse_args()

    # Execute task (None if no task provided - orchestrator will handle this)
    task = " ".join(args.task) if args.task else None
    interactive = not args.no_interactive  # Interactive by default
    asyncio.run(execute_task(task, interactive=interactive, traces_dir=args.traces_dir))


if __name__ == "__main__":
    main()