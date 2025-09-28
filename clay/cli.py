"""CLI interface for Clay."""

import asyncio
import sys
from pathlib import Path

from clay.orchestrator.orchestrator import ClayOrchestrator


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: clay <task>")
        sys.exit(1)

    task = " ".join(sys.argv[1:])

    # Create traces directory for CLI
    traces_dir = Path("_trace")
    traces_dir.mkdir(exist_ok=True)

    try:
        # Execute the task with automatic trace saving
        orchestrator = ClayOrchestrator(traces_dir=traces_dir)
        await orchestrator.process_task(task)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())