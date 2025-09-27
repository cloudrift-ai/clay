"""CLI interface for Clay."""

import asyncio
import sys

from clay.orchestrator.orchestrator import ClayOrchestrator


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: clay <task>")
        sys.exit(1)

    task = " ".join(sys.argv[1:])
    orchestrator = ClayOrchestrator()
    await orchestrator.process_task(task)


if __name__ == "__main__":
    asyncio.run(main())